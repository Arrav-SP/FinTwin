# FinTwin Phase 3 — Telemetry Results

Phase 3 connected the Phase 2 workload generator to real PostgreSQL and host telemetry.

## Verified experiment

The recorded experiment produced:

| Metric | Measured value |
|---|---:|
| Telemetry samples | 11 |
| Telemetry errors | 0 |
| Error rate | 0% |
| P50 latency | 9.2585 ms |
| P95 latency | 13.3134 ms |
| P99 latency | 23.0085 ms |
| Database commit delta | 461 |
| Database rollback delta | 159 |
| Deadlock delta | 0 |
| Cache hit ratio | 99.689% |
| Average host CPU | 8.0727% |
| Average host memory | 92.0727% |
| Database size before | 10,730,519 bytes |
| Database size after | 10,828,823 bytes |

## Collected telemetry

The system persisted initial, periodic, and final samples containing PostgreSQL activity, transaction counters, lock information, database size, cache-hit ratio, and host CPU/memory readings. The experiment summary was linked to the same experiment ID as the workload operations.

The experiment observed zero blocked sessions and zero ungranted lock waits. The `waiting_connections` field represents PostgreSQL wait events generally and should not be interpreted as lock contention by itself.

## Test status

The complete regression suite later reported:

```text
11 passed, 2 warnings
```

The warnings were non-failing FastAPI/Starlette deprecation warnings.

