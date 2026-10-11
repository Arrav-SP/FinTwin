from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

import json

from . import access, archive
from .auth import router as auth_router
from .bundled import install_bundled
from .config import get_settings
from .database import check_connection, engine, initialize_schema
from .jobs import JobManager
from .ml.dataset import INTERRUPTED_EXTRA_SECONDS, INTERRUPTED_FACTOR
from .telemetry import TelemetryCollector
from .telemetry.metrics import latency_breakdown, summary_select
from .ui import mount_ui
from .validation import get_validation, list_validations, made_since, run_validation, validation_summary
from .workload import Scenario, WorkloadConfig, WorkloadRunner
from .workload.config import DEFAULT_MIXES
from .limits import MAX_DURATION_SECONDS, MAX_TARGET_TPS
from .workload.config import MAX_CONCURRENCY


APP_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = APP_ROOT / "web" / "dist"

app = FastAPI(title="FinTwin API", version="8.0.0")
# A fresh copy of the project has no trained models; install the ones shipped with it.
install_bundled()
app.include_router(auth_router)


@app.on_event("startup")
def _bring_schema_up_to_date() -> None:
    """Add any table or column a newer version of the code expects. The schema file is idempotent."""
    try:
        initialize_schema()
    except SQLAlchemyError:
        pass  # the database may not be up yet; /api/health reports that
    if access.config().public:
        # Importing the ML stack and unpickling the models takes many seconds on a small host.
        # Do it now, off the request path, so the first visitor's prediction is quick.
        import threading

        def warm() -> None:
            try:
                from .ml.predict import warm as load_models

                load_models()
            except Exception:
                pass

        threading.Thread(target=warm, name="fintwin-warm", daemon=True).start()
jobs = JobManager()
# Site-run counts at which a retraining was already queued, so one batch of runs queues one training.
_training_attempted_at: list[int] = []


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


def _require_visible(experiment_id: str, request: Request) -> None:
    """404 for a run that does not exist or that belongs to someone else: the two look the same."""
    with engine.connect() as connection:
        row = connection.execute(text("SELECT started_by FROM experiment_runs WHERE experiment_id = :id"), {"id": experiment_id}).first()
    if row is None or not access.may_see(row[0], request):
        raise HTTPException(status_code=404, detail="Experiment not found")


def _without_owner(record: dict[str, Any]) -> dict[str, Any]:
    record = dict(record)
    record.pop("started_by", None)
    return record


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
    # On a public server: how many runs have been made here, and how many are needed before the models are retrained on them.
    site: dict[str, Any] = {"site_runs": None, "site_runs_needed": None}
    try:
        if access.config().public:
            from .ml import retrain

            site = {"site_runs": retrain.site_runs(), "site_runs_needed": get_settings().site_min_runs}
        with engine.connect() as connection:
            telemetry_count = connection.execute(text("SELECT COUNT(*) FROM telemetry_samples")).scalar_one()
        return {"database": "connected", "telemetry": "active" if telemetry_count else "awaiting_data", "ml_models": "ready" if model_count else "unavailable", "telemetry_samples": telemetry_count, "model_artifacts": model_count, **site}
    except SQLAlchemyError:
        return {"database": "offline", "telemetry": "unavailable", "ml_models": "ready" if model_count else "unavailable", "telemetry_samples": None, "model_artifacts": model_count, **site}


@app.get("/api/experiments")
def experiments(request: Request, limit: int = 100, include_interrupted: bool = False) -> list[dict[str, Any]]:
    """Recent runs. A run that lasted several times its requested duration was suspended with the
    machine; its figures measure the pause, so it is listed only on request."""
    try:
        with engine.connect() as connection:
            rows = connection.execute(text(f"""
                SELECT e.experiment_id, e.scenario, e.configuration, e.started_at, e.completed_at, e.status,
                       e.actual_tps, e.average_latency_ms, e.p50_latency_ms, e.p95_latency_ms, e.p99_latency_ms,
                       e.successful_operations, e.failed_operations, s.host_cpu_avg_percent, s.lock_wait_count_max,
                       s.telemetry_sample_count,
                       COALESCE(e.started_by = :login, FALSE) AS mine,
                       e.started_by IS NULL AS reference
                FROM experiment_runs e
                LEFT JOIN experiment_summaries s USING (experiment_id)
                WHERE {access.visible("e")}
                  AND (:include_interrupted OR NOT COALESCE(
                    EXTRACT(EPOCH FROM e.completed_at - e.started_at) > GREATEST(:factor * (e.configuration->>'duration_seconds')::float,
                                                                          (e.configuration->>'duration_seconds')::float + :extra), FALSE))
                ORDER BY e.started_at DESC LIMIT :limit
            """), {"limit": max(1, min(limit, 500)), "include_interrupted": include_interrupted, "factor": INTERRUPTED_FACTOR, "extra": INTERRUPTED_EXTRA_SECONDS, **access.viewer(request)}).mappings().all()
        result = []
        for row in rows:
            record = dict(row)
            record["configuration"] = _configuration(record["configuration"])
            result.append(record)
        return result
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@app.get("/api/experiments/{experiment_id}")
def experiment_detail(experiment_id: str, request: Request) -> dict[str, Any]:
    try:
        with engine.connect() as connection:
            experiment = connection.execute(text(f"""
                SELECT e.*, {summary_select("s")}
                FROM experiment_runs e LEFT JOIN experiment_summaries s USING (experiment_id)
                WHERE e.experiment_id = :id
            """), {"id": experiment_id}).mappings().first()
            if experiment is None or not access.may_see(experiment["started_by"], request):
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
        owner = record.pop("started_by", None)  # who ran it is shown to nobody else
        record["mine"] = owner is not None and owner == access.current_login(request)
        record["reference"] = owner is None
        record["configuration"] = _configuration(record["configuration"])
        return {"experiment": record, "telemetry": [dict(item) for item in telemetry], "validations": [dict(item) for item in validations]}
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@app.post("/api/predictions", dependencies=[Depends(access.limit_predictions)])
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


@app.post("/api/what-if", dependencies=[Depends(access.limit_predictions)])
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
def recommendations(experiment_id: str, request: Request) -> dict[str, Any]:
    try:
        _require_visible(experiment_id, request)
        from .optimization import analyze_experiment

        return analyze_experiment(experiment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@app.get("/api/validation")
def validations(request: Request, limit: int = 100, scope: Literal["all", "current"] = "all") -> list[dict]:
    """`scope=current` keeps only checks predicted by the models now on disk."""
    try:
        records = made_since(list_validations(max(1, min(limit, 1000))), _since(scope))
        return [_without_owner(record) for record in records if access.may_see(record.get("started_by"), request)]
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@app.get("/api/validation/summary")
def validations_summary(scope: Literal["all", "current"] = "all") -> dict:
    try:
        return validation_summary(_since(scope))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@app.get("/api/validation/{validation_id}")
def validation_detail(validation_id: str, request: Request) -> dict:
    try:
        record = get_validation(validation_id)
        if not access.may_see(record.get("started_by"), request):
            raise ValueError(f"Validation not found: {validation_id}")
        return _without_owner(record)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@app.post("/api/validation", status_code=201)
def create_validation(request: ValidationRequest) -> dict:
    if access.config().public:
        raise HTTPException(status_code=403, detail="On this server, validations are started from the Validation page after signing in.")
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


@app.post("/api/what-if/sweep", dependencies=[Depends(access.limit_predictions)])
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
def experiment_latency(experiment_id: str, request: Request) -> dict[str, Any]:
    try:
        _require_visible(experiment_id, request)
        with engine.connect() as connection:
            events = connection.execute(text("SELECT operation, latency_ms, queue_wait_ms, success FROM workload_events WHERE experiment_id = :id"), {"id": experiment_id}).mappings().all()
            if not events:
                # A run restored from the archive has no events, only the summary stored when it finished.
                stored = connection.execute(text("SELECT latency_breakdown FROM experiment_summaries WHERE experiment_id = :id"), {"id": experiment_id}).scalar()
                if stored:
                    return stored if isinstance(stored, dict) else json.loads(stored)
        return latency_breakdown(events)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


def _run_workload_job(config: WorkloadConfig, telemetry_interval: float, login: str | None = None) -> dict[str, Any]:
    result = WorkloadRunner(config, started_by=login).run(TelemetryCollector(telemetry_interval))
    return {"experiment_id": str(result.experiment_id)}


def _run_validation_job(config: WorkloadConfig, telemetry_interval: float, login: str | None = None) -> dict[str, Any]:
    record = run_validation(config, telemetry_interval=telemetry_interval, started_by=login)
    if record["validation_status"] != "COMPLETED":
        raise RuntimeError(record.get("error_message") or "Validation did not complete")
    return jsonable_encoder({"validation_id": record["validation_id"], "experiment_id": record["actual_experiment_id"]})


def _after_run(experiment_id: str | None) -> None:
    """Keep the run's latency summary with it (its events are not archived) and push it to the archive."""
    if experiment_id:
        with engine.connect() as connection:
            events = connection.execute(text("SELECT operation, latency_ms, queue_wait_ms, success FROM workload_events WHERE experiment_id = :id"), {"id": experiment_id}).mappings().all()
        with engine.begin() as connection:
            connection.execute(text("UPDATE experiment_summaries SET latency_breakdown = CAST(:breakdown AS JSONB) WHERE experiment_id = :id"), {"breakdown": json.dumps(latency_breakdown(events), default=float), "id": experiment_id})
    archive.sync()
    _queue_retraining_if_due()


def _queue_retraining_if_due() -> None:
    """On a public server, retrain on site runs once there are enough, and again after each further batch.

    The training goes through the job queue, so it never runs beside a measurement.
    """
    if not access.config().public:
        return
    from .ml import retrain

    count = retrain.site_runs()
    last = max([retrain.trained_at_runs() or 0, *_training_attempted_at]) or None
    if retrain.due(count, last):
        _training_attempted_at.append(count)
        jobs.submit("training", {}, lambda: retrain.retrain(site_runs=count), owner=None)


def _authorize_run(http: Request, request: JobRequest) -> str | None:
    """On a public server only a signed-in person may run, within the caps and their daily allowance."""
    if not access.config().public:
        return None
    login = access.current_login(http)
    if login is None:
        raise HTTPException(status_code=401, detail="Sign in with GitHub to run a workload on this server.")
    workload = request.workload
    access.check_public_caps(workload.concurrency, workload.target_tps, workload.duration_seconds)
    if archive.is_full():
        raise HTTPException(status_code=503, detail="The site's storage is full, so new runs are paused. Reading and predicting still work.")
    if access.runs_used(login) >= access.RUNS_PER_DAY:
        raise HTTPException(status_code=429, detail=f"You have used today's {access.RUNS_PER_DAY} runs. The allowance refills over the next 24 hours.")
    if jobs.waiting() >= access.MAX_WAITING:
        raise HTTPException(status_code=429, detail="Several runs are already waiting. Try again in a minute.")
    return login


@app.post("/api/jobs", status_code=202)
def submit_job(request: JobRequest, http: Request) -> dict[str, Any]:
    login = _authorize_run(http, request)
    try:
        config = request.config()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    work = _run_workload_job if request.kind == "workload" else _run_validation_job

    if login:
        access.record_run(login, request.kind)
    def run() -> dict[str, Any]:
        result = work(config, request.telemetry_interval, login)
        _after_run(result.get("experiment_id"))
        return result

    return jobs.submit(request.kind, request.model_dump(mode="json"), run, owner=login)


@app.get("/api/jobs")
def list_jobs(request: Request) -> list[dict[str, Any]]:
    """On a public server, only the signed-in person's own jobs."""
    if not access.config().public:
        return jobs.list()
    login = access.current_login(request)
    return jobs.list(owner=login) if login else []


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: str, request: Request) -> dict[str, Any]:
    if access.config().public:
        login = access.current_login(request)
        job = jobs.get(job_id, owner=login) if login else None
    else:
        job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# Last, so that it only answers addresses no API route claimed.
mount_ui(app, WEB_ROOT)
