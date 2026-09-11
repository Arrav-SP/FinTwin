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

Phase 1 is complete. Phase 2 workload generation is complete. Phase 3 telemetry is complete. Phase 4 ML dataset diagnostics and leakage-safe training/prediction infrastructure are implemented, but model training is intentionally gated until more measured workload diversity exists. What-if prediction, optimization recommendations, validation dashboards, and cloud infrastructure remain future phases.

Measured Phase 4 dataset and model results are recorded in [docs/PHASE4_RESULTS.md](docs/PHASE4_RESULTS.md). Results are preliminary because the current dataset contains seven usable experiment summaries.

Historical phase results: [Phase 1](docs/PHASE1_RESULTS.md), [Phase 2](docs/PHASE2_RESULTS.md), and [Phase 3](docs/PHASE3_RESULTS.md).

## Phase 5 — What-If Analysis

Phase 5 compares Phase 4 model predictions for baseline and hypothetical workloads without executing them. It supports parameter changes, concurrency/TPS sweeps, JSON/CSV output, and model-derived sensitivity. Sensitivity describes learned associations within the training distribution; it is not causal proof. Predictions are strongest inside the observed training range, and Phase 4 warnings are preserved.

```powershell
python scripts/what_if.py --scenario NORMAL_DAY --concurrency 50 --target-tps 100 --change-concurrency 100 --output-json artifacts/what-if.json
python scripts/what_if.py --scenario NORMAL_DAY --concurrency 50 --target-tps 100 --sweep-concurrency 25 50 75 100 --output-csv artifacts/concurrency-sweep.csv
```

The measured Phase 5 what-if outputs are recorded in [docs/PHASE5_RESULTS.md](docs/PHASE5_RESULTS.md).

## Phase 6 — Intelligent Optimization Recommendations

Phase 6 analyzes measured telemetry and generates explainable, advisory bottleneck recommendations. It reuses Phase 3 evidence and handles unavailable `pg_stat_statements` gracefully. It never changes the database automatically. See [docs/PHASE6_OPTIMIZATION.md](docs/PHASE6_OPTIMIZATION.md).

The verified Phase 6 assessment is recorded in [docs/PHASE6_RESULTS.md](docs/PHASE6_RESULTS.md).

## Phase 7 — Predicted-vs-Actual Validation

Phase 7 adds validation infrastructure that keeps ML predictions separate from measured PostgreSQL observations. A validation run stores a prediction, executes the identical `WorkloadConfig` through the Phase 2 runner, collects Phase 3 telemetry, links the resulting `experiment_id`, and calculates absolute/percentage errors. Failed predictions, unavailable PostgreSQL, missing telemetry, and invalid configurations are persisted as `FAILED` records with diagnostics; no synthetic performance labels are created.

Initialize the new table before using the CLI:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python scripts/initialize_database.py
python scripts/validate_prediction.py --scenario NORMAL_DAY --concurrency 10 --target-tps 10 --duration 10 --output artifacts/validation.json
python scripts/run_validation_suite.py --scenarios NORMAL_DAY SALARY_DAY --duration 10 --output artifacts/validation-summary.json
python scripts/run_benchmark.py --scenarios NORMAL_DAY SALARY_DAY --duration 10 --format csv --output artifacts/benchmark.csv
```

The safe suite defaults to two scenarios, 10 concurrent workers, 10 TPS, and one 10-second repetition. Increase duration, repetitions, or workload intensity explicitly when collecting more evidence. The API exposes `POST /api/validation`, `GET /api/validation`, `GET /api/validation/{validation_id}`, and `GET /api/validation/summary`.

`run_benchmark.py` is the model-independent benchmark path. It executes real PostgreSQL workloads and exports measured experiment results, so it can be used before a complete model set exists.

Validation metrics are reported only for completed runs with both predicted and actual values. MAE, RMSE, R², and MAPE are omitted or set to null when their inputs are unavailable or mathematically undefined (for example, percentage error with an actual value of zero). See [docs/PHASE7_VALIDATION.md](docs/PHASE7_VALIDATION.md).

The first measured Phase 7 result is recorded in [docs/PHASE7_RESULTS.md](docs/PHASE7_RESULTS.md). It completed successfully, but showed material prediction error: 49.75% for average latency, 66.52% for P95 latency, 20.57% for throughput, and 50.54% for host CPU. These are preliminary results from one real validation configuration, not statistically meaningful overall accuracy claims.

