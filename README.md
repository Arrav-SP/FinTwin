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

## Phase 2 workload generator

Phase 2 adds reproducible banking workloads without changing the six Phase 1 banking entities. Each run creates a unique experiment ID, records its configuration in `experiment_runs`, and records per-operation latency, success/failure, and errors in `workload_events`.

After applying the updated schema, run a workload from PowerShell:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python scripts/run_workload.py --scenario NORMAL_DAY --concurrency 4 --target-tps 10 --duration 10 --seed 42
```

Available scenarios include `NORMAL_DAY`, `SALARY_DAY`, `MONTH_END`, `FESTIVAL_SPIKE`, `CARD_PAYMENT_SPIKE`, `LOAN_PROCESSING`, and `HIGH_CONCURRENCY_TRANSFER`. Target TPS is the requested pacing; `actual_tps` is measured from completed operations. Workload execution uses SQLAlchemy's pooled connections and bounded thread concurrency.

## Project status and future phases

Phase 1 is complete. Phase 2 workload generation is implemented. Telemetry, ML, what-if prediction, optimization recommendations, validation dashboards, and cloud infrastructure remain future phases.

