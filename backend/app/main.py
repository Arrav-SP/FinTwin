from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .database import check_connection, engine
from .validation import get_validation, list_validations, run_validation, validation_summary
from .workload import Scenario, WorkloadConfig

app = FastAPI(title="FinTwin Phase 1 API", version="1.0.0")


class ValidationRequest(BaseModel):
    scenario: Scenario = Scenario.NORMAL_DAY
    concurrency: int = Field(default=10, ge=1)
    target_tps: float = Field(default=10.0, gt=0)
    duration_seconds: float = Field(default=10.0, gt=0)
    seed: int = 42
    telemetry_interval: float = Field(default=1.0, gt=0)


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

