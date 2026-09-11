from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .database import check_connection, engine

app = FastAPI(title="FinTwin Phase 1 API", version="1.0.0")


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

