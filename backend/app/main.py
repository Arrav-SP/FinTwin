from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .database import check_connection, engine
from .validation import get_validation, list_validations, run_validation, validation_summary
from .workload import Scenario, WorkloadConfig

APP_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = APP_ROOT / "frontend"

app = FastAPI(title="FinTwin API", version="7.0.0")
app.mount("/assets", StaticFiles(directory=FRONTEND_ROOT), name="assets")


class ValidationRequest(BaseModel):
    scenario: Scenario = Scenario.NORMAL_DAY
    concurrency: int = Field(default=10, ge=1)
    target_tps: float = Field(default=10.0, gt=0)
    duration_seconds: float = Field(default=10.0, gt=0)
    seed: int = 42
    telemetry_interval: float = Field(default=1.0, gt=0)


class WorkloadRequest(BaseModel):
    scenario: Scenario = Scenario.NORMAL_DAY
    concurrency: int = Field(default=10, ge=1)
    target_tps: float = Field(default=10.0, gt=0)
    duration_seconds: float = Field(default=10.0, gt=0)
    operation_mix: dict[str, float] | None = None
    burstiness: float = Field(default=0.0, ge=0, le=1)

    def workload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class WhatIfRequest(BaseModel):
    baseline: WorkloadRequest
    modified: WorkloadRequest


def _configuration(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(FRONTEND_ROOT / "index.html")


@app.get("/styles.css", include_in_schema=False)
def frontend_styles() -> FileResponse:
    return FileResponse(FRONTEND_ROOT / "styles.css", media_type="text/css")


@app.get("/app.js", include_in_schema=False)
def frontend_script() -> FileResponse:
    return FileResponse(FRONTEND_ROOT / "app.js", media_type="text/javascript")


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
def experiments(limit: int = 100) -> list[dict[str, Any]]:
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT e.experiment_id, e.scenario, e.configuration, e.started_at, e.completed_at, e.status,
                       e.actual_tps, e.average_latency_ms, e.p50_latency_ms, e.p95_latency_ms, e.p99_latency_ms,
                       e.successful_operations, e.failed_operations, s.host_cpu_avg_percent, s.lock_wait_count_max,
                       s.telemetry_sample_count
                FROM experiment_runs e
                LEFT JOIN experiment_summaries s USING (experiment_id)
                ORDER BY e.started_at DESC LIMIT :limit
            """), {"limit": max(1, min(limit, 500))}).mappings().all()
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
            experiment = connection.execute(text("""
                SELECT e.*, s.* FROM experiment_runs e LEFT JOIN experiment_summaries s USING (experiment_id)
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
def validations(limit: int = 100) -> list[dict]:
    try:
        return list_validations(max(1, min(limit, 1000)))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@app.get("/api/validation/summary")
def validations_summary() -> dict:
    try:
        return validation_summary()
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

