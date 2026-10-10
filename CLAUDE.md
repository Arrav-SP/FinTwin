# FinTwin: working notes for Claude

Read this first. It records what has already been verified so the codebase does not need to be re-audited from scratch. Last full audit: 2026-10-09. Re-check a fact against the code only if the relevant file has changed since then.

## Standing rules from the user

- **No Git or GitHub changes** without explicit permission in the current message: no commit, push, stage, branch, tag, reset, config or remote edits. Read-only Git only.
- Git currently refuses to run in this folder ("dubious ownership": `.git` is owned by another Windows user). The fix is a `safe.directory` config change, which needs the user's permission. Work from the filesystem instead.
- Do not overwrite existing reports. Do not change source code unless asked.
- Treat source code as the authority; the README, `docs/` and the PPTs are partly outdated.

## What the project is

A database-performance test bench, not a personal-finance or LLM app. There is no LLM, no RAG, no user accounts, no real financial data. It runs synthetic banking workloads against PostgreSQL 16, records telemetry, trains scikit-learn regressors to predict performance from workload configuration, and validates predictions against real runs. Course: Database Systems Project (B.Tech CSE, VIT Vellore). Team: Arav Singh Patel (24BCE2425), Chaitanya Ghogare (24BCE2392).

## Layout

| Path | Contents |
|---|---|
| `database/schema.sql` | 6 banking tables (branches, customers, accounts, merchants, transactions, loans), 5 platform tables (experiment_runs, workload_events, telemetry_samples, experiment_summaries, validation_experiments), 15 explicit indexes |
| `backend/app/main.py` | FastAPI app, 18 `/api` endpoints, serves `frontend/` |
| `backend/app/services/transfer_service.py` | `transfer_funds`: one transaction, both rows locked `ORDER BY account_id FOR UPDATE` |
| `backend/app/workload/` | `config.py` (7 scenarios, 7 operation types, `WorkloadConfig`), `runner.py` (thread pool, open-loop pacing) |
| `backend/app/telemetry/` | `collector.py` (1 s sampler over pg_stat_activity, pg_stat_database, pg_locks, psutil), `metrics.py` |
| `backend/app/ml/` | `dataset.py`, `features.py` (`remainder="drop"`), `models.py` (`build_model`, `RateShare`), `train.py` (LR / RF / GBM, 5-fold GroupKFold by load setting, best by MAE, refit on all runs), `predict.py` (range warnings), `registry.py` |
| `backend/app/what_if.py`, `optimization.py`, `validation.py` | comparison and sweeps; six threshold rules; predict-run-compare |
| `frontend/` | Old UI, still served by FastAPI at port 8000: `index.html`, `styles.css`, `app.js`; six views; no framework. To be retired when `web/` covers every page |
| `web/` | New UI (F1, redesigned 2026-10-10). React 19 + TypeScript + Vite 8 + Tailwind 4 + TanStack Query + React Router 8 + Recharts. Read `web/DESIGN.md` before touching it. Tokens in `src/styles.css`; top-bar shell in `src/app/`; typed API in `src/api/`; pages Overview, Experiments, run detail (`/experiments/:id`, includes the advisor), Run, Predict, What if, Validation, Models (F2 and F3, 2026-10-10). There is no separate Advisor page and no two-workload comparison; the old UI's features are otherwise covered. Rule: measured = filled signal colour, predicted = hollow dashed. Serif Newsreader for statements, IBM Plex Sans for the interface. No cards, no sidebar, no icons |
| `scripts/` | CLI entry points (seed, run_workload, train_models, what_if, validate_prediction, run_benchmark, ...) |
| `tests/` | 8 modules, 24 cases; only `test_phase1.py` (4 cases) needs PostgreSQL |
| `artifacts/` | git-ignored: 5 models (`.joblib` + `.json`), `validation.json`, `benchmark.csv`, sweep CSVs |
| `docs/` | phase result notes (`PHASE1..7_RESULTS.md`), partly outdated |

## Running it (Windows PowerShell, from the project root)

- Use `.venv-ml` (Python 3.11). `.venv` (Python 3.14) cannot load NumPy on this machine.
- The folder was moved, so venv launcher `.exe` files are broken. Always use `python -m ...` (`python -m uvicorn backend.app.main:app`, `python -m pytest`).
- Start Docker Desktop, then `docker compose up -d`; set `$env:PYTHONPATH = (Get-Location).Path`.
- Models load from the relative path `artifacts/models`, so run from the project root.
- Offline tests: `python -m pytest -p no:cacheprovider --ignore=tests/test_phase1.py` gave 20 passed on 2026-10-09. `test_phase1.py` mutates account balances in the live database.
- `scripts/seed_database.py` truncates and reloads the six banking tables.

## Verified facts worth remembering

- Latency is timed inside the worker: excludes pacing sleep, thread-pool queueing and the event insert. Since M1 it no longer includes an account lookup (ids are loaded once per run and all active accounts are eligible).
- `WorkloadConfig` has `burstiness` (0 = even spacing, 1 = exponential gaps, same mean rate) and `account_skew` (0 = uniform, higher = Zipf-like hot accounts). Both are model features. `scripts/run_workload.py` takes `--burstiness` and `--account-skew`.
- Concurrency is capped at `MAX_CONCURRENCY = 64` (`backend/app/limits.py`); the pool is sized to match. The validation endpoint also caps TPS at 1000 and duration at 600 s.
- Host CPU and memory are machine-wide. The CPU average skips the INITIAL sample.
- Models on disk were retrained in M3 (2026-10-10) on 247 runs; see the M3 section. Burstiness is still 0 in every training run.
- Runs made before 2026-10-10 measured latency with the old lookup included, so they are not comparable with newer runs. Do not mix them in one training set.
- Contention is now reachable: HIGH_CONCURRENCY_TRANSFER, 32 workers, 400 TPS, skew 1.5 gave 31 ungranted locks, 30 blocked sessions, 275 actual TPS, 0 deadlocks (2026-10-10).

## Milestone 1 (done 2026-10-10)

Fixed, each with a test in `tests/test_m1_logic.py` or `tests/test_m1_database.py`: detail/advisor NULL overwrite; failed runs now marked `FAILED` with telemetry stopped; `max_connections` stored in `experiment_summaries` (advisor connection rule now live); what-if default duration; R-squared withheld when all validations share one configuration; input bounds. Full suite: 43 passed (`python -m pytest -p no:cacheprovider`, database up).

## Running the new UI

`.claude/launch.json` defines `fintwin-api` (port 8000) and `fintwin-web` (Vite, port 5173, proxies `/api`). Manually: `npm --prefix web run dev`. Checks: `npm --prefix web test` (65 tests), `npm --prefix web run typecheck`, `npm --prefix web run build`. Bash heredocs containing JSX or triple quotes fail in this environment; use the Write tool for such files. Browser screenshots only work while the Browser pane is displayed; otherwise verify through the DOM.

## Milestone 2 (done 2026-10-10): API for the new UI

Tests in `tests/test_m2_logic.py` and `tests/test_m2_database.py`. Full backend suite: 61 passed.

| Endpoint | Purpose |
|---|---|
| `POST /api/jobs` (202), `GET /api/jobs`, `GET /api/jobs/{id}` | Run a workload or a validation in the background. `backend/app/jobs.py`: in-memory, one job at a time so measurements never overlap; jobs are lost on restart, their experiments are not. Body: `{kind: "workload"|"validation", workload: {...}, seed, telemetry_interval}` |
| `GET /api/models` | Per-target model card from `artifacts/models/*.json` plus `trained_at` (`ml/registry.py`) |
| `GET /api/scenarios` | The seven default mixes and the input limits |
| `POST /api/what-if/sweep` | `{baseline, parameter: "concurrency"|"target_tps", values}` -> predictions per value and sensitivity |
| `GET /api/experiments/{id}/latency` | Per-operation latency and queue-wait statistics plus a 1-2-5 histogram |

`workload_events.queue_wait_ms` now records how long each operation waited for a worker; latency remains service time only. `WorkloadRequest` accepts `account_skew` and is bounded like the validation request. The API has 18 endpoints. The old synchronous `POST /api/validation` is kept for the old UI.

## Milestone 3 (done 2026-10-10): campaign and retraining

Tests in `tests/test_m3_ml.py`. Full backend suite: 74 passed.

- `scripts/run_campaign.py`: `--design grid` (7 scenarios x 5 load levels x 2 skews, shuffled, repeated) and `--design random` (workers 2-64 and rate 10-600 drawn log-uniformly, skew 0 / 0.6 / 1.2). Run: grid 140 runs (`artifacts/campaign.json`), random 100 runs (`artifacts/campaign-random.json`). No failed runs, no deadlocks.
- **Keep the machine awake during a campaign.** It slept during the random one; two runs lasted 31 min and 8 h. `rows_to_frame` now flags `interrupted` (elapsed > 3x requested duration; legitimate runs overrun by at most 1.6x) and `training_rows` drops them. The two rows are still in the database.
- Training set: 247 runs, 176 configurations, 109 load settings; 32 runs with lock waits, 29 saturated. Pre-M1 runs are excluded by `current_timing`.
- Evaluation: 5-fold `GroupKFold` grouped by `load_key` (workers|rate), so every model is scored at loads it never saw. Grouping by configuration alone overstated accuracy: grid-only models looked good in CV and then missed off-grid throughput by 25-40%.
- Throughput is modelled as a share of the requested rate (`RateShare`), so it follows rates it has not seen.
- Metadata per model: `candidates`, `baseline` (requested rate for throughput, scenario mean otherwise), `repeat_spread`, `held_out`, `cv_folds`, `configurations`.
- CV MAE, chosen model vs baseline (repeat spread): avg latency RF 3.42 vs 15.22 (1.01); P95 RF 23.9 vs 48.4 (5.10), R2 only 0.42; throughput RF 6.63 vs 15.45 (3.32); CPU linear 5.80 vs 13.48 (2.35); lock waits RF 2.04 vs 4.39 (0.38).
- 16 fresh validations after retraining (`artifacts/m3-validation.json`), model MAE vs baseline: avg latency 3.67 vs 9.54; P95 14.0 vs 24.4; throughput 5.10 vs 9.71 (model closer in only 9 of 16: below saturation the requested rate is already near-exact); CPU 3.75 vs 10.46; lock waits 0.97 vs 2.19.
- Known weakness: above about 350 TPS the models over-predict latency (up to 2x) and lock waits, and under-predict throughput by 2-8%, on workloads that turn out not to saturate. Few training runs there. Candidates for M4: more high-load runs, longer runs.
- The database now holds 20+ validation records made with three different generations of models; the Validation page aggregates them all. Worth separating by model version in F4 or M4.
- Models from before M3 are in `..\FinTwin_backup_2026-10-10\models_before_m3`.

## Known open issues

1. `frontend/app.js` defines `validationPage` twice (goes away with the frontend rebuild).
2. API has no authentication; PostgreSQL port 5432 is published by Docker. Local use only.
3. Endpoints return plain dicts, so the OpenAPI schema has no response types; the `web/` types are written by hand in `src/api/types.ts`.
4. `README.md`, `docs/` and both PPT decks are out of date (planned for M4).

## Documents

- Final report: `FinTwin_Final_Project_Review_Report.docx` and `.pdf` (31 pages, built 2026-10-09 from `FinTwin_Project_Review_1_Report_Clean.docx` as the base). It says one validation run was recorded; the database actually holds three. Correct this at the next revision.
- The report was generated with python-docx plus Word export; the build scripts were temporary and are not in the repository.
- `PROJECT_EXPLANATION.docx` is about an unrelated Linux-timer project.
- Both decks in `PPTs/` describe 10 entities and a React dashboard; the code has 6 banking tables and plain HTML/JS.
- `README.md` contradicts itself on project status; `docs/PHASE7_VALIDATION.md` says there is no frontend.

## Current state of work

Roadmap approved by the user on 2026-10-10, to be done one milestone at a time with a checkpoint after each. Changes stay local: no commits, no pushes. A source backup and a database dump from before M1 are in `..\FinTwin_backup_2026-10-10`.

Order: M1 backend correctness (done) -> F1 frontend foundation (done 2026-10-10) (React + TypeScript + Vite, design tokens, app shell, typed API client, Overview page) -> M2 new API endpoints (done 2026-10-10) -> F2 core pages (done 2026-10-10: run detail, Predict, What if) -> F3 action pages (done 2026-10-10) -> M3 experiment campaign and retraining (done 2026-10-10) -> F4 polish (next) -> M4 study, report and slides.

Open decisions: the user has not said whether they want an LLM copilot (default: no, build an evidence-based "Analyst" panel) and has not given a deadline. Installing npm packages for F1 needs their go-ahead.
