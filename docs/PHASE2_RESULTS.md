# FinTwin Phase 2 — Workload Generator Results

Phase 2 added configurable, reproducible banking workloads on top of the Phase 1 database.

## Capabilities

- Scenario-based operation mixes
- Configurable concurrency, target TPS, duration, and random seed
- Concurrent PostgreSQL workers using the SQLAlchemy connection pool
- Unique experiment IDs
- Per-operation latency and success/failure logging
- Requested TPS kept separate from measured actual TPS

## Verified workload runs

| Scenario | Concurrency | Target TPS | Operations | Successful | Actual TPS | Average latency |
|---|---:|---:|---:|---:|---:|---:|
| NORMAL_DAY | 4 | 10 | 100 | 100 | 10.0855 | 9.2341 ms |
| NORMAL_DAY | 8 | 20 | 200 | 200 | 20.0689 | 9.3317 ms |
| SALARY_DAY | 4 | 10 | 100 | 100 | 10.0880 | 10.5454 ms |
| FESTIVAL_SPIKE | 8 | 20 | 200 | 200 | 20.0641 | 10.6691 ms |
| HIGH_CONCURRENCY_TRANSFER | 12 | 30 | 300 | 300 | 30.0608 | 11.8446 ms |
| LOAN_PROCESSING | 4 | 15 | 150 | 150 | 15.0885 | 6.8301 ms |

All six recorded runs completed successfully with zero failed operations. These measurements became part of the Phase 3 telemetry dataset and later Phase 4 ML dataset.

