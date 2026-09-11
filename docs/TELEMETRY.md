# Phase 3 Telemetry

Phase 3 records measured workload, PostgreSQL, and host behaviour for each Phase 2 experiment. It does not generate synthetic metrics or train ML models.

`telemetry_samples` stores timestamped initial, periodic, and final snapshots linked to the existing experiment ID. `experiment_summaries` stores percentile latency, error rate, connection/lock maxima, database counter deltas, cache hit ratio, database size, and host CPU/memory aggregates. PostgreSQL metrics come from `pg_stat_activity`, `pg_stat_database`, `pg_locks`, and `pg_database_size`. Host metrics are machine-level `psutil` readings, not PostgreSQL CPU alone.

Run a monitored experiment with `python scripts/run_workload.py --scenario NORMAL_DAY --concurrency 4 --target-tps 10 --duration 10 --telemetry-interval 1`. Target TPS is requested pacing; actual TPS is completed operations divided by elapsed time. Percentiles use actual operation latency samples. If a telemetry sample fails, the workload continues and `telemetry_error_count` records the issue.

Phase 4 can consume `experiment_runs`, `workload_events`, `telemetry_samples`, and `experiment_summaries` directly. P99 should be interpreted cautiously for small samples; `pg_stat_statements` remains optional.
