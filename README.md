# FinTwin

FinTwin is a performance test bench for PostgreSQL. It runs synthetic banking workloads against a live PostgreSQL 16 database, records what happened, trains regression models that predict performance from the workload configuration alone, and checks those predictions against real runs.

It is not a banking application. All data is synthetic, there are no user accounts, and nothing connects to a real financial system. There is no language model in the project; the models are scikit-learn regressors.

## What it does

1. **Generate.** Seven scenarios (normal day, salary day, month end, festival spike, card payment spike, loan processing, high-concurrency transfer) mix seven operation types. A run is set by workers, requested rate (TPS), duration, burstiness and hot-account skew.
2. **Observe.** Every operation's latency, queue wait and outcome is stored. A sampler records PostgreSQL statistics and host CPU and memory once a second.
3. **Learn.** One model per metric (average latency, P95 latency, throughput, host CPU, lock waits) is chosen from linear regression, random forest and gradient boosting by cross-validation that holds out whole load settings.
4. **Predict.** A workload is predicted without running it, with a warning when it lies outside what the models were trained on.
5. **Validate.** The prediction is stored first, then the same workload is run and the two are compared.

## Current results

Measured on one development machine with runs of eight seconds. Details and limits are in [docs/RESULTS.md](docs/RESULTS.md).

- 280 recorded runs, 383,385 operations, no deadlocks. Loads up to 600 TPS with 64 workers reach lock contention and saturation.
- Models trained on 247 runs beat a no-model baseline on every metric, in cross-validation and on 16 workloads predicted before they were run (mean error 3.7 ms for average latency, 5.1 TPS for throughput).
- The models are accurate below about 350 TPS and weak above it. P95 latency is the least reliable target.

## Stack

PostgreSQL 16 in Docker; Python 3.11+ with FastAPI, SQLAlchemy 2 Core, psycopg 3, pandas and scikit-learn; a React, TypeScript and Vite interface in `web/`; pytest and Vitest for tests.

## Quick start with Docker

This needs only Docker. It builds the interface and the API, starts PostgreSQL, and on a new database loads the recorded runs and the trained models that the report is based on.

```powershell
Copy-Item .env.example .env
docker compose --profile app up -d --build
```

Open `http://127.0.0.1:8000/` once the build finishes (a few minutes the first time). Stop it with `docker compose --profile app down`.

What you get is the author's data and models. Every page works at once, and you can run new workloads and validations. Two things to know:

- The models were trained on the author's laptop. On another machine, and inside a container, the measured latency and especially host CPU will differ from the predictions. To get models for your own machine, run the two campaigns and `train_models.py` (see below).
- The server listens on `127.0.0.1` only. The API has no authentication and is not meant to be exposed.

## Public website

FinTwin can be published as a free public site where anyone can read the results and predict, and people signed in with GitHub can run small, capped workloads. The step-by-step guide is [docs/DEPLOY.md](docs/DEPLOY.md). Public mode is off unless `FINTWIN_PUBLIC=true` is set; a server on your own machine is unrestricted.

## Setup without Docker for the application (Windows PowerShell, from the project root)

Use this for development. PostgreSQL still runs in Docker; `docker compose up -d` starts only the database.

```powershell
Copy-Item .env.example .env
docker compose up -d
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt -c backend/constraints.txt
$env:PYTHONPATH = (Get-Location).Path
python scripts/initialize_database.py
python scripts/seed_database.py
```

`backend/constraints.txt` pins the library versions the shipped models were saved with; a scikit-learn model file is only guaranteed to load with the version that wrote it.

On a new database volume PostgreSQL loads `bundled/database.sql.gz` (the recorded runs), so the two `scripts/` lines above are only needed if you removed that file or want to reset the banking tables. The seed is deterministic (`seed = 42`): 100 branches, 1,000 customers, 1,500 accounts, 100 merchants, 5,000 transactions and 200 loans. `seed_database.py` truncates and reloads those six tables.

Build the interface once (and again after changing anything in `web/`), then start the server:

```powershell
npm --prefix web install
npm --prefix web run build
python -m uvicorn backend.app.main:app
```

Open `http://127.0.0.1:8000/`. The same server answers the API under `/api`. The API has no authentication and is meant for local use only.

If `artifacts/models` is empty, the server installs the shipped models from `bundled/models` when it starts. Models you train yourself are never replaced.

## Using it

From the interface: **Run** starts a workload, **Predict** estimates one, **What if** sweeps workers or rate, **Validation** predicts and then runs, **Models** shows each model's error beside the no-model baseline and the run-to-run variation.

From the command line:

```powershell
python scripts/run_workload.py --scenario NORMAL_DAY --concurrency 16 --target-tps 100 --duration 8 --account-skew 1.2
python scripts/run_campaign.py --design grid --repetitions 2
python scripts/run_campaign.py --design random --runs 100 --output artifacts/campaign-random.json
python scripts/train_models.py
python scripts/run_study.py
python scripts/predict_workload.py --scenario NORMAL_DAY --concurrency 16 --target-tps 100
python scripts/what_if.py --concurrency 32 --target-tps 100 --sweep-tps 50 100 200 300 400 600
python scripts/validate_prediction.py --scenario NORMAL_DAY --concurrency 12 --target-tps 100
```

A campaign takes 15 to 25 minutes. Keep the machine awake while it runs: a run interrupted by sleep is detected and left out of training, but it is lost.

## Tests

```powershell
python -m pytest
npm --prefix web test
```

The backend suite has 120 cases; fifteen need PostgreSQL running and seeded, and `tests/test_phase1.py` changes account balances. The interface has 82 tests.

## Layout

| Path | Contents |
|---|---|
| `database/schema.sql` | Six banking tables, five experiment tables, constraints and indexes |
| `backend/app/` | FastAPI app, workload runner, telemetry collector, ML pipeline (`ml/`), what-if, advisor, validation, background jobs |
| `web/` | The interface. Design rules are in `web/DESIGN.md` |
| `scripts/` | Command-line entry points |
| `tests/` | Backend tests |
| `docs/` | Results and design notes. Files named `PHASE*` are historical |
| `bundled/` | Shipped with the project: the trained models, the campaign, validation and study records, and a dump of the database |
| `artifacts/` | Working copy of models and results on this machine (not in version control) |
| `Dockerfile`, `docker-compose.yml` | The database service, and the application service under the `app` profile |
| `deploy/space/`, `scripts/build_space.py` | The all-in-one image for the public website, and the script that assembles the folder pushed to the host |

`frontend/` holds the first, plain HTML interface. It is no longer served.
