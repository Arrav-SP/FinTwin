# FinTwin

FinTwin is an AI-powered banking database performance simulator. Phase 1 establishes the PostgreSQL foundation only: schema, synthetic data, Python connectivity, an atomic transfer service, and two FastAPI verification endpoints.

FinTwin uses synthetic banking data and is not connected to real financial systems.

## Stack

PostgreSQL 16, Docker Compose, Python 3.11+, FastAPI, SQLAlchemy 2.x, psycopg 3, Pydantic Settings, and pytest.

## Setup (PowerShell)

```powershell
Copy-Item .env.example .env
docker compose up -d
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
$env:PYTHONPATH = (Get-Location).Path
python scripts/initialize_database.py
python scripts/seed_database.py
```

The seed is deterministic (`seed = 42`) and creates 100 branches, 1,000 customers, 1,500 accounts, 100 merchants, 5,000 transactions, and 200 loans.

## API and tests

```powershell
$env:PYTHONPATH = (Get-Location).Path
uvicorn backend.app.main:app --reload
pytest
```

Endpoints: `GET /api/health` checks the live PostgreSQL connection; `GET /api/database/summary` returns live row counts. The integration tests verify tables, seeded counts, transfer commit behavior, insufficient-balance rollback, and both endpoints. PostgreSQL must be running and seeded before executing them.

## Project structure

`database/schema.sql` contains the repeatable schema and indexes. `backend/app` contains configuration, SQLAlchemy connectivity, the FastAPI app, and transfer service. `scripts` contains initialization and deterministic seeding. `tests` contains integration tests. `docs/database_design.md` records the normalization and transaction design.

## Project status and future phases

Phase 1 intentionally does not include React, ML, workload simulation, telemetry, optimization recommendations, or cloud infrastructure. Future phases may add workload generation and observability only after this database foundation is verified.

