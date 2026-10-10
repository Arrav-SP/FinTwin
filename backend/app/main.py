from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .bundled import install_bundled
from .database import check_connection, engine
from .jobs import JobManager
from .ml.dataset import INTERRUPTED_FACTOR
from .telemetry import TelemetryCollector
from .telemetry.metrics import latency_breakdown, summary_select
from .ui import mount_ui
from .validation import get_validation, list_validations, made_since, run_validation, validation_summary
from .workload import Scenario, WorkloadConfig, WorkloadRunner
from .workload.config import DEFAULT_MIXES
from .workload.config import MAX_CONCURRENCY

MAX_TARGET_TPS = 1000.0
MAX_DURATION_SECONDS = 600.0

APP_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = APP_ROOT / "web" / "dist"

app = FastAPI(title="FinTwin API", version="8.0.0")
# A fresh copy of the project has no trained models; install the ones shipped with it.
install_bundled()
jobs = JobManager()


class ValidationRequest(BaseModel):
    scenario: Scenario = Scenario.NORMAL_DAY
    concurrency: int = Field(default=10, ge=1, le=MAX_CONCURRENCY)
    target_tps: float = Field(default=10.0, gt=0, le=MAX_TARGET_TPS)
    duration_seconds: float = Field(default=10.0, gt=0, le=MAX_DURATION_SECONDS)
    seed: int = 42
    telemetry_interval: float = Field(default=1.0, gt=0)


class WorkloadRequest(BaseModel):
    scenario: Scenario = Scenario.NORMAL_DAY
    concurrency: int = Field(default=10, ge=1, le=MAX_CONCURRENCY)
    target_tps: float = Field(default=10.0, gt=0, le=MAX_TARGET_TPS)
    duration_seconds: float = Field(default=10.0, gt=0, le=MAX_DURATION_SECONDS)
    operation_mix: dict[str, float] | None = None
    burstiness: float = Field(default=0.0, ge=0, le=1)
    account_skew: float = Field(default=0.0, ge=0, le=3)

    def workload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class WhatIfRequest(BaseModel):
    baseline: WorkloadRequest
    modified: WorkloadRequest


class SweepRequest(BaseModel):
    baseline: WorkloadRequest
    parameter: Literal["concurrency", "target_tps"]
    values: list[float] = Field(min_length=2, max_length=24)


class JobRequest(BaseModel):
    kind: Literal["workload", "validation"]
    workload: WorkloadRequest
    seed: int = 42
    telemetry_interval: float = Field(default=1.0, gt=0, le=10)

    def config(self) -> WorkloadConfig:
        w = self.workload
        return WorkloadConfig(scenario=w.scenario, concurrency=w.concurrency, target_tps=w.target_tps, duration_seconds=w.duration_seconds, operation_mix=w.operation_mix, seed=self.seed, burstiness=w.burstiness, account_skew=w.account_skew)


def _configuration(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _models_trained_at() -> datetime | None:
    """When the stored models were written, or None when there are none."""
    from .ml.registry import describe_models

    stamps = [datetime.fromisoformat(model["trained_at"]) for model in describe_models()]
    return max(stamps) if stamps else None


def _since(scope: str) -> datetime | None:
    return _models_trained_at() if scope == "current" else None


@app.get("/api/health")
def health() -> dict[str, str]:
    try:
        check_connection()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ok", "database": "connected"}


@app.get("/api/database/summary")
def database_summary() -> dict[str, int]:
    tables = ("branches", "customers", "accounts", "merchants", "transactions", "loans")
    try:
        with engine.connect() as connection:
            return {table: connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() for table in tables}
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@app.get("/api/system/status")
def system_status() -> dict[str, Any]:
    model_directory = APP_ROOT / "artifacts" / "models"
    model_count = len(list(model_directory.glob("*.joblib"))) if model_directory.exists() else 0
    try:
        with engine.connect() as connection:
            telemetry_count = connection.execute(text("SELECT COUNT(*) FROM telemetry_samples")).scalar_one()
        return {"database": "connected", "telemetry": "active" if telemetry_count else "awaiting_data", "ml_models": "ready" if model_count else "unavailable", "telemetry_samples": telemetry_count, "model_artifacts": model_count}
    except SQLAlchemyError:
        return {"database": "offline", "telemetry": "unavailable", "ml_models": "ready" if model_count else "unavailable", "telemetry_samples": None, "model_artifacts": model_count}


@app.get("/api/experiments")
def experiments(limit: int = 100, include_interrupted: bool = False) -> list[dict[str, Any]]:
    """Recent runs. A run that lasted several times its requested duration was suspended with the
    machine; its figures measure the pause, so it is listed only on request."""
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT e.experiment_id, e.scenario, e.configuration, e.started_at, e.completed_at, e.status,
                       e.actual_tps, e.average_latency_ms, e.p50_latency_ms, e.p95_latency_ms, e.p99_latency_ms,
                       e.successful_operations, e.failed_operations, s.host_cpu_avg_percent, s.lock_wait_count_max,
                       s.telemetry_sample_count
                FROM experiment_runs e
                LEFT JOIN experiment_summaries s USING (experiment_id)
                WHERE :include_interrupted OR NOT COALESCE(
                    EXTRACT(EPOCH FROM e.completed_at - e.started_at) > :factor * (e.configuration->>'duration_seconds')::float, FALSE)
                ORDER BY e.started_at DESC LIMIT :limit
            """), {"limit": max(1, min(limit, 500)), "include_interrupted": include_interrupted, "factor": INTERRUPTED_FACTOR}).mappings().all()
        result = []
        for row in rows:
            record = dict(row)
            record["configuration"] = _configuration(record["configuration"])
            result.append(record)
        return result
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@app.get("/api/experiments/{experiment_id}")
def experiment_detail(experiment_id: str) -> dict[str, Any]:
    try:
        with engine.connect() as connection:
            experiment = connection.execute(text(f"""
                SELECT e.*, {summary_select("s")}
                FROM experiment_runs e LEFT JOIN experiment_summaries s USING (experiment_id)
                WHERE e.experiment_id = :id
            """), {"id": experiment_id}).mappings().first()
            if experiment is None:
                raise HTTPException(status_code=404, detail="Experiment not found")
            telemetry = connection.execute(text("""
                SELECT sample_kind, captured_at, active_connections, waiting_connections, blocked_sessions,
                       lock_wait_count, cache_hit_ratio, host_cpu_percent, host_memory_percent
                FROM telemetry_samples WHERE experiment_id = :id ORDER BY captured_at DESC LIMIT 100
            """), {"id": experiment_id}).mappings().all()
            validations = connection.execute(text("""
                SELECT validation_id, validation_status, predicted_metrics, actual_metrics, error_metrics, created_at
                FROM validation_experiments WHERE actual_experiment_id = :id ORDER BY created_at DESC
            """), {"id": experiment_id}).mappings().all()
        record = dict(experiment)
        record["configuration"] = _configuration(record["configuration"])
        return {"experiment": record, "telemetry": [dict(item) for item in telemetry], "validations": [dict(item) for item in validations]}
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@app.post("/api/predictions")
def create_prediction(request: WorkloadRequest) -> dict[str, Any]:
    try:
        from .ml.predict import predict_performance

        return {"workload": request.workload(), **predict_performance(request.workload())}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="ML prediction is unavailable") from exc


@app.post("/api/what-if")
def what_if(request: WhatIfRequest) -> dict[str, Any]:
    try:
        from .what_if import compare_workloads

        return compare_workloads(request.baseline.workload(), request.modified.workload())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="What-if analysis is unavailable") from exc


@app.get("/api/recommendations/{experiment_id}")
def recommendations(experiment_id: str) -> dict[str, Any]:
    try:
        from .optimization import analyze_experiment

        return analyze_experiment(experiment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@app.get("/api/validation")
def validations(limit: int = 100, scope: Literal["all", "current"] = "all") -> list[dict]:
    """`scope=current` keeps only checks predicted by the models now on disk."""
    try:
        return made_since(list_validations(max(1, min(limit, 1000))), _since(scope))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@app.get("/api/validation/summary")
def validations_summary(scope: Literal["all", "current"] = "all") -> dict:
    try:
        return validation_summary(_since(scope))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@app.get("/api/validation/{validation_id}")
def validation_detail(validation_id: str) -> dict:
    try:
        return get_validation(validation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@app.post("/api/validation", status_code=201)
def create_validation(request: ValidationRequest) -> dict:
    try:
        config = WorkloadConfig(scenario=request.scenario, concurrency=request.concurrency, target_tps=request.target_tps, duration_seconds=request.duration_seconds, seed=request.seed)
        return run_validation(config, telemetry_interval=request.telemetry_interval)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc



@app.get("/api/scenarios")
def scenarios() -> dict[str, Any]:
    return {
        "scenarios": [{"scenario": scenario.value, "operation_mix": mix} for scenario, mix in DEFAULT_MIXES.items()],
        "limits": {"max_concurrency": MAX_CONCURRENCY, "max_target_tps": MAX_TARGET_TPS, "max_duration_seconds": MAX_DURATION_SECONDS},
    }


@app.get("/api/models")
def models() -> list[dict[str, Any]]:
    from .ml.registry import describe_models

    return describe_models(APP_ROOT / "artifacts" / "models")


@app.post("/api/what-if/sweep")
def what_if_sweep(request: SweepRequest) -> dict[str, Any]:
    try:
        from .what_if import sensitivity_analysis

        values = [int(value) for value in request.values] if request.parameter == "concurrency" else request.values
        return sensitivity_analysis(request.baseline.workload(), request.parameter, values)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/experiments/{experiment_id}/latency")
def experiment_latency(experiment_id: str) -> dict[str, Any]:
    try:
        with engine.connect() as connection:
            exists = connection.execute(text("SELECT 1 FROM experiment_runs WHERE experiment_id = :id"), {"id": experiment_id}).first()
            if exists is None:
                raise HTTPException(status_code=404, detail="Experiment not found")
            events = connection.execute(text("SELECT operation, latency_ms, queue_wait_ms, success FROM workload_events WHERE experiment_id = :id"), {"id": experiment_id}).mappings().all()
        return latency_breakdown(events)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


def _run_workload_job(config: WorkloadConfig, telemetry_interval: float) -> dict[str, Any]:
    result = WorkloadRunner(config).run(TelemetryCollector(telemetry_interval))
    return {"experiment_id": str(result.experiment_id)}


def _run_validation_job(config: WorkloadConfig, telemetry_interval: float) -> dict[str, Any]:
    record = run_validation(config, telemetry_interval=telemetry_interval)
    if record["validation_status"] != "COMPLETED":
        raise RuntimeError(record.get("error_message") or "Validation did not complete")
    return jsonable_encoder({"validation_id": record["validation_id"], "experiment_id": record["actual_experiment_id"]})


@app.post("/api/jobs", status_code=202)
def submit_job(request: JobRequest) -> dict[str, Any]:
    try:
        config = request.config()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    work = _run_workload_job if request.kind == "workload" else _run_validation_job
    return jobs.submit(request.kind, request.model_dump(mode="json"), lambda: work(config, request.telemetry_interval))


@app.get("/api/jobs")
def list_jobs() -> list[dict[str, Any]]:
    return jobs.list()


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: str) -> dict[str, Any]:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# Last, so that it only answers addresses no API route claimed.
mount_ui(app, WEB_ROOT)
