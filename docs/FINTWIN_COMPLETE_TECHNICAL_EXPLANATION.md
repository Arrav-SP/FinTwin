# FINTWIN — COMPLETE CODEBASE DEEP-DIVE & TECHNICAL EXPLANATION

## 1. What is FinTwin?
* **One-sentence explanation:** FinTwin is an AI-powered banking database performance simulator that uses machine learning to predict how a PostgreSQL database will perform under various synthetic banking workloads without having to actually run them.
* **30-second explanation:** Traditional database stress testing is time-consuming and expensive. FinTwin solves this by running a small set of real banking workloads against a PostgreSQL database, capturing detailed telemetry, and training machine learning models on this data. These models can then instantly predict database performance (latency, throughput, CPU) for new, hypothetical workload configurations via "What-If" analysis. 
* **2-minute explanation:** FinTwin acts as a scoped "digital twin" for a banking database's performance characteristics. It starts with a synthetic but normalized relational banking schema (branches, customers, accounts, loans). It uses a Python-based workload generator to execute highly concurrent transactions (like atomic fund transfers and payments). During execution, a telemetry collector repeatedly polls PostgreSQL internal statistics (`pg_stat_activity`, `pg_stat_database`, `pg_locks`) alongside host CPU and memory. 
  
  Once enough experiments are recorded, a machine learning pipeline (using scikit-learn tree-based and linear models) learns the mapping from pre-execution workload features (concurrency, target TPS, operation mix) to post-execution performance metrics (P95 latency, actual TPS, CPU usage). Finally, the system allows engineers to perform instant What-If analysis to predict scaling behavior and validates those predictions by running the actual workloads again and comparing predicted vs. actual metrics.
* **Complete Technical Explanation:** Read the rest of this document.

## 2. The Problem Being Solved
**What problem does FinTwin solve?**
Testing database performance against infinite variations of workloads (spikes in traffic, month-end batch processing, different API payload mixes) is functionally impossible to do exhaustively. Stress testing requires provisioning heavy infrastructure, executing long-running workloads, and waiting for results. 

**Why is database performance prediction useful?**
It allows teams to forecast infrastructure exhaustion and latency degradation instantly. By having a model, you can do capacity planning in milliseconds instead of hours.

**Why is PostgreSQL used?**
PostgreSQL is a robust, ACID-compliant relational database. It exposes deep internal statistics via system views (like `pg_stat_statements` and `pg_locks`) which are perfect for extracting rich telemetry.

**Why are banking workloads appropriate?**
Banking workloads are highly transactional, requiring ACID properties (especially Atomicity and Isolation) and row-level locking for fund transfers. This creates realistic database contention, deadlocks, and nonlinear performance degradation under pressure, making it an excellent candidate for ML prediction.

**What does "digital twin" mean in THIS project?**
It means a predictive model of the database's *performance behavior* under specific operational stress. It does NOT mean a full functional twin of a bank's business logic, user interfaces, or external payment gateways.

---

## 3. Complete Project Map & Data Flow
Here is the conceptual flow and architecture of FinTwin, derived directly from the implementation:

```mermaid
flowchart TD
    USER[User / Developer] --> |Configures Workload| FRONT[Frontend UI (HTML/JS)]
    FRONT --> |API Request| API[FastAPI Backend (backend/app/main.py)]
    API --> |WorkloadConfig| RUNNER[Workload Runner (backend/app/workload/runner.py)]
    RUNNER --> |SQL Transactions| PG[(PostgreSQL 16)]
    RUNNER --> |Start/Stop| TELEM[Telemetry Collector (backend/app/telemetry/collector.py)]
    TELEM --> |Polls stats| PG
    TELEM --> |Saves Samples| PG
    RUNNER --> |Saves Events| PG
    
    PG --> |Extracts Dataset| ML[ML Pipeline (backend/app/ml/train.py)]
    ML --> |Trains Models| MODELS[Model Artifacts (.joblib)]
    
    API --> |What-If / Predict| PREDICT[Prediction Engine (backend/app/ml/predict.py)]
    PREDICT --> |Reads| MODELS
    PREDICT --> |Returns| FRONT
    
    API --> |Validation Request| VALID[Validation Engine (backend/app/validation.py)]
    VALID --> |Predicts| PREDICT
    VALID --> |Executes Real Workload| RUNNER
    VALID --> |Calculates Errors| VALID
```

### Flow Breakdown
1. **Application Startup:** The FastAPI application (`backend/app/main.py`) starts up via `uvicorn`, loading DB configuration from `backend/app/config.py`. It mounts static frontend files.
2. **Workload Generation:** The user submits a workload request (Scenario, Concurrency, Target TPS). The backend generates transactions using `WorkloadRunner`, connecting to PostgreSQL via SQLAlchemy.
3. **Telemetry Collection:** As threads execute SQL, a background thread (`TelemetryCollector`) polls PostgreSQL internal tables every second, storing snapshots in `telemetry_samples`.
4. **Machine Learning:** `train_models.py` extracts completed `experiment_runs` and `experiment_summaries`. It trains models (Linear Regression, Random Forest, Gradient Boosting) mapping configuration (inputs) to performance (targets).
5. **Prediction & What-If:** The `predict_performance` function loads `.joblib` models and infers metrics for new workload configurations instantly. `compare_workloads` compares a baseline configuration vs. a modified one.
6. **Validation:** `validate_prediction.py` predicts performance, actually executes the workload on PostgreSQL, gathers real telemetry, and calculates Absolute Error, Percentage Error, MAE, etc.

---

## 4. Phase 1 — Database Foundation

**A. Objective:** Establish a realistic, normalized relational banking database.
**B. Problem:** Real banking data is private. We need a realistic schema and synthetic data to simulate a banking core.
**C. What was implemented:** PostgreSQL 16 schema (`database/schema.sql`), Python initialization/seed scripts (`scripts/initialize_database.py`, `scripts/seed_database.py`), and atomic transfer logic (`backend/app/services/transfer_service.py`).
**D. Files involved:** 
- `database/schema.sql` (DDL and indexes)
- `backend/app/services/transfer_service.py` (atomic transfer)
**E. Database Interaction:**
- `branches` (100 rows)
- `customers` (1,000 rows)
- `accounts` (1,500 rows)
- `merchants` (100 rows)
- `transactions` (5,000 rows)
- `loans` (200 rows)
All tables use `BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY`. Foreign keys strictly enforce relationships (e.g., `accounts` -> `customers`, `transactions` -> `accounts`).
**F. Important Implementation Decisions:**
- **Deadlock Avoidance:** The atomic `transfer_funds` uses `SELECT ... FOR UPDATE` to lock rows in ascending Account ID order. This mathematically prevents deadlocks when concurrent transfers happen between the same two accounts in reverse directions.

---

## 5. Phase 2 — Workload Generation

**A. Objective:** Generate concurrent database transactions simulating banking operations.
**B. Problem:** We need reproducible, configurable workloads to generate varied performance data.
**C. What was implemented:** Scenario-based operations (`NORMAL_DAY`, `SALARY_DAY`, `MONTH_END`, etc.) executed concurrently via `ThreadPoolExecutor`.
**D. Files involved:** `backend/app/workload/runner.py`, `backend/app/workload/config.py`
**E. Inputs:** `Scenario`, `concurrency`, `target_tps`, `duration_seconds`, `operation_mix`, `seed`.
**F. Processing:** 
- `WorkloadRunner` uses a `ThreadPoolExecutor` bounded by `concurrency`.
- To hit `target_tps`, the runner sleeps dynamically based on `perf_counter()` offset.
- `OperationResult` captures per-operation success and latency.
**G. Outputs:** Inserts into `experiment_runs` and `workload_events`.
**H. Important Implementation Decisions:**
- Target TPS is pacing; Actual TPS is measured as `completed_operations / elapsed_time`.

---

## 6. Phase 3 — Telemetry

**A. Objective:** Observe PostgreSQL behavior during workloads.
**B. Problem:** We need to know *why* a workload was slow, not just that it was slow.
**C. What was implemented:** A threaded `TelemetryCollector` polling PostgreSQL system views.
**D. Files involved:** `backend/app/telemetry/collector.py`, `backend/app/telemetry/metrics.py`
**E. Metrics Collected (Verified in Code):**
- **From pg_stat_activity:** `active_connections`, `idle_connections`, `waiting_connections`, `blocked_sessions`
- **From pg_stat_database:** `xact_commit`, `xact_rollback`, `blks_read`, `blks_hit`, `deadlocks`
- **From pg_locks:** `lock_count`, `lock_wait_count`
- **Host metrics:** `host_cpu_percent`, `host_memory_percent` (via `psutil`)
**F. Processing:**
An initial snapshot is taken. A loop samples every `interval_seconds`. A final snapshot is taken. Deltas (e.g., commits) are calculated. P50, P95, P99 latencies are aggregated from `workload_events`.
**G. Outputs:** Inserts into `telemetry_samples` and `experiment_summaries`.
**H. Important Implementation Decisions:**
- Latency is calculated inside the `OperationResult` timer, deliberately *excluding* the artificial pacing sleep.

---

## 7. Phase 4 — Machine Learning

**A. Objective:** Train models to predict database performance from workload parameters.
**B. Problem:** Traditional testing requires running every permutation. ML can interpolate and extrapolate instantly.
**C. What was implemented:** A scikit-learn pipeline transforming features and training regressors.
**D. Files involved:** `backend/app/ml/train.py`, `backend/app/ml/dataset.py`, `backend/app/ml/features.py`, `backend/app/ml/predict.py`
**E. Inputs (Features):**
- Categorical: `scenario` (OneHotEncoded)
- Numeric: `concurrency`, `target_tps`, `duration_seconds`, `burstiness`, and operation ratios (`balance_check_ratio`, `transfer_ratio`, etc.).
**F. Outputs (Targets):**
`average_latency_ms`, `p95_latency_ms`, `actual_tps`, `host_cpu_avg_percent`, `lock_wait_count_max`
**G. ML Interaction:**
- The system trains `LinearRegression`, `RandomForestRegressor`, and `GradientBoostingRegressor`.
- Evaluates based on MAE (Mean Absolute Error) and selects the best algorithm per target.
- Saves `.joblib` pipelines and `.json` metadata.
**H. Data Leakage Prevention (CRITICAL):**
No post-execution telemetry (like cache hit ratio or active connections) is fed into the features. Only parameters known *before* execution are used as features. Training uses `GroupShuffleSplit` on `configuration_key` so the model is tested on genuinely unseen workload shapes.

---

## 8. Phase 5 — What-If Analysis

**A. Objective:** Answer "What happens if I double concurrency?" without running it.
**B. Problem:** Need instant capacity forecasting.
**C. What was implemented:** A prediction comparator calculating deltas and sensitivities.
**D. Files involved:** `backend/app/what_if.py`
**E. Processing:**
`compare_workloads` runs `predict_performance` on a baseline config and a modified config, returning absolute and percentage changes.
**F. Important Implementation Decisions:**
- **Correlation vs. Causation:** The analysis outputs *model-derived sensitivity*, demonstrating how the ML model's weights react. This is clearly documented as NOT causal proof. 
- **Out of Distribution Warnings:** It explicitly returns warnings if a feature value (e.g., `concurrency=100`) exceeds the training bounds recorded in `numeric_ranges`.

---

## 9. Phase 6 — Optimization

**A. Objective:** Generate rule-based recommendations based on measured telemetry.
**B. Problem:** Raw metrics are hard to interpret. We need actionable advice.
**C. What was implemented:** An advisory bottleneck rules engine.
**D. Files involved:** `backend/app/optimization.py`
**E. Processing:**
Checks metrics against thresholds (e.g., `cpu_high: 80.0`, `cache_low: 95.0`, `tail_ratio_high: 2.0`). Generates severities (`HIGH`, `MEDIUM`).
**F. Outputs:** Evidence-based recommendations.
**G. Important Implementation Decisions:**
- It is strictly advisory. It never modifies PostgreSQL configuration or creates indexes automatically. 
- It attempts to fetch `pg_stat_statements` but fails gracefully with a warning if the extension is unavailable, refusing to invent query evidence.

---

## 10. Phase 7 — Validation + Benchmarking

**A. Objective:** Prove the model's accuracy against reality.
**B. What was implemented:** A scientific validation loop that predicts, runs, and measures.
**C. Files involved:** `backend/app/validation.py`, `scripts/validate_prediction.py`
**D. Processing (The Validation Loop):**
1. Receives a `WorkloadConfig`.
2. Predicts targets using loaded ML models. Stores as `PENDING`.
3. Runs the actual workload via `WorkloadRunner` against real Postgres.
4. Updates record to `COMPLETED`, linking `actual_experiment_id`.
5. Calculates Absolute Error and Percentage Error per metric.
**E. Testing & Metrics:**
Aggregates validation records calculating MAE, RMSE, R², and MAPE. Errors are mathematically omitted if actual values are zero (to avoid DivisionByZero).

---

## 11. Database Management Systems Deep Dive

**Where does FinTwin demonstrate DBMS concepts?**
1. **Relational Model & ER Modeling:** Phase 1 defines strict relations (`branches` -> `customers` -> `accounts`).
2. **Primary / Foreign Keys:** `account_id` is a PK. `transactions` holds `from_account_id` and `to_account_id` as FKs.
3. **Constraints:** `CHECK (balance >= 0)`, `CHECK (currency = 'INR')`, `CHECK (end_date > start_date)`.
4. **Transactions & ACID:** 
   - **Atomicity:** `transfer_funds` debits and credits inside a single Python context manager (`engine.begin()`). If insufficient funds raise an exception, the context manager rolls back.
   - **Consistency:** `balance >= 0` check constraint prevents negative balances.
   - **Isolation:** `SELECT ... FOR UPDATE` locks rows, preventing concurrent dirty writes.
   - **Durability:** Confirmed by querying the database after commit.
5. **Concurrency & Locking:** Highly concurrent workloads generate contention. Lock waits and blocked sessions are explicitly polled from `pg_locks` and `pg_stat_activity`.
6. **PostgreSQL Statistics:** Actively leverages `pg_stat_database` (commits, rollbacks, cache hits) and `pg_stat_activity` (active connections).

---

## 12. Complete Data Flow (Example: SALARY_DAY)

1. **User Submission:** User requests a `SALARY_DAY` workload with concurrency 10 via the API (`POST /api/predictions` or validation endpoint).
2. **Configuration:** The backend extracts the `SALARY_DAY` operation mix (35% Deposit, 25% Balance Check, 20% Transfer, etc.).
3. **Execution (`WorkloadRunner`):** Spawns 10 threads. A thread picks `DEPOSIT` based on weights, selects an account, issues `SELECT ... FOR UPDATE`, updates the balance, and logs to `transactions`.
4. **Telemetry (`TelemetryCollector`):** Meanwhile, a daemon thread polls `pg_stat_activity` and `psutil` every 1 second.
5. **Aggregation:** Run finishes. Latency P95 is calculated from `workload_events`. Telemetry deltas are saved to `experiment_summaries`.
6. **ML Pipeline:** `train.py` reads these summaries, extracts features, trains a Random Forest on `P95_latency`.
7. **Prediction:** User asks "What if concurrency is 50?" `predict_performance` loads the model, passes `concurrency=50`, and returns a predicted latency.
8. **Validation:** `validate_prediction.py` runs the prediction, then actually runs concurrency 50, and records the 66% percentage error showing the model underestimated the tail latency.

---

## 13. File-by-File Explanation

* **`database/schema.sql`**: The absolute truth of the data model. Contains `CREATE TABLE` and `CREATE INDEX` for business entities and FinTwin telemetry tables.
* **`backend/app/workload/config.py`**: Defines `Scenario` Enum, `DEFAULT_MIXES` weights, and `WorkloadConfig` dataclass.
* **`backend/app/workload/runner.py`**: Contains `WorkloadRunner`. Uses `ThreadPoolExecutor` to execute transactions and log `workload_events`.
* **`backend/app/services/transfer_service.py`**: Contains `transfer_funds` with the ordered `SELECT FOR UPDATE` deadlock avoidance logic.
* **`backend/app/telemetry/collector.py`**: The background threaded poller that reads PostgreSQL system views.
* **`backend/app/ml/dataset.py`**: Queries raw DB tables and transforms them into a Pandas DataFrame, defining features and target constants.
* **`backend/app/ml/features.py`**: Contains the scikit-learn `ColumnTransformer` (OneHotEncoding for scenarios).
* **`backend/app/ml/train.py`**: Splits data, trains multiple regressors, selects the best via MAE, and saves `.joblib` models.
* **`backend/app/ml/predict.py`**: Loads `.joblib` models, constructs a DataFrame from a workload dictionary, predicts targets, and calculates OOD warnings.
* **`backend/app/what_if.py`**: Compares two workload configurations using `predict_performance`.
* **`backend/app/optimization.py`**: Evaluates experiment metrics against static `Thresholds` to yield recommendations.
* **`backend/app/validation.py`**: The orchestration logic tying prediction and `WorkloadRunner` together for accuracy calculation.
* **`backend/app/main.py`**: The FastAPI application serving REST endpoints and static files.

---

## 14. Testing Architecture
The `tests/` directory contains pytest suites.
- **`test_phase1.py`**: Verifies schema constraints, seed data row counts, and tests atomic transfer rollback logic on insufficient funds.
- **`test_workload.py`**: Validates that workloads execute successfully and respect requested bounds.
- **`test_telemetry.py`**: Validates metrics gathering.
- **`test_ml.py` / `test_what_if.py` / `test_optimization.py` / `test_validation.py`**: Unit test their respective domain logic.

---

## 15. Limitations & Future Work

**Current Limitations:**
- **Small Dataset:** As noted in `PHASE4_RESULTS.md`, the dataset has only 7 usable experiments. ML models extrapolating from this are highly inaccurate (e.g., negative R² for latency).
- **Synthetic Data:** Real banking payloads have highly variable network sizes and skewed access distributions (e.g., zipfian distributions of "whale" accounts), which pure random sampling misses.
- **Non-Causal What-If:** The What-If analysis demonstrates model feature sensitivity, not physical causality.

**Future Work:**
- Run massive, multi-hour permutation sweeps across a distributed cluster to build a statistically significant ML dataset.
- Implement learned index recommendations using real query plan parsing (`EXPLAIN ANALYZE`).
- Transition to production telemetry streams rather than synthetic load tests.

---

## 16. VIVA Preparation Questions

**Q: Why PostgreSQL?**
A: PostgreSQL provides deep, real-time internal statistics via catalog views (`pg_stat_activity`, `pg_stat_statements`). This allows non-intrusive telemetry collection crucial for creating a digital twin, alongside robust ACID compliance necessary for realistic banking locks.

**Q: Why ML instead of traditional benchmarking?**
A: Benchmarking is discrete and expensive. You cannot physically run a benchmark for every integer value of concurrency from 1 to 10,000. ML allows us to execute a bounding set of benchmarks, learn the performance manifold, and interpolate/extrapolate predictions instantly.

**Q: Why use P95 latency instead of only average?**
A: Average latency hides tail behavior. In databases, resource exhaustion (like lock queues or thread starvation) causes exponential degradation for a small percentage of queries first. P95 captures this degraded user experience accurately.

**Q: How does the system prevent data leakage in ML?**
A: Target variables (like actual TPS or lock waits) and post-execution telemetry (like cache hits) are strictly excluded from the `make_preprocessor()` features pipeline. The model is only allowed to see pre-execution configuration parameters (`concurrency`, `target_tps`, `scenario`).

**Q: What is the difference between Target TPS and Actual TPS?**
A: Target TPS is the *requested* pacing parameter fed into the workload generator. Actual TPS is the mathematically measured throughput (`completed_operations / elapsed_time`). A database under pressure will fail to achieve the Target TPS, making Actual TPS a predictable target variable.

**Q: Explain how FinTwin prevents deadlocks during transfers.**
A: In `transfer_service.py`, when transferring between Account A and Account B, the code explicitly sorts the Account IDs numerically and locks them in ascending order (`SELECT FOR UPDATE`). This prevents classic deadlocks where Thread 1 locks A then B, while Thread 2 locks B then A.

---

## 17. 5-Minute Viva Cheat Sheet
* **Project:** FinTwin
* **Problem:** Database stress testing is expensive and slow; capacity planning requires instant answers.
* **Solution:** Machine Learning predicting PostgreSQL performance based on synthetic workload telemetry.
* **Architecture:** FastAPI -> SQLAlchemy -> Postgres 16 -> Scikit-Learn -> Joblib -> FastAPI.
* **Telemetry:** `pg_stat_activity` (connections/blocks), `pg_stat_database` (commits/blks), `pg_locks`.
* **ML:** Predicts P95 Latency, CPU, TPS using Random Forest / Gradient Boosting.
* **What-If:** Instant non-causal sensitivity analysis.
* **Validation:** Computes MAE/MAPE by running predictions against real DB runs.
* **Novelty:** Complete end-to-end integration of a synthetic banking engine with live telemetry and local ML prediction without relying on third-party SaaS tracing tools.
* **Biggest Limitation:** The training dataset is currently too small (7 runs) for production accuracy.

---
*End of Technical Explanation*
