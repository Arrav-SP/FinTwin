# FinTwin Phase 6 — Optimization Assessment Results

This assessment analyzed experiment `13c4ef00-b7ba-4f9f-9dd6-ed141e00ebea` from a real `NORMAL_DAY` PostgreSQL workload.

## Measured performance

| Metric | Value |
|---|---:|
| Actual TPS | 10.0848 |
| Average latency | 9.8387 ms |
| P50 latency | 9.2585 ms |
| P95 latency | 13.3134 ms |
| P99 latency | 23.0085 ms |
| Error rate | 0% |
| Maximum active connections | 1 |
| Blocked sessions | 0 |
| Lock waits | 0 |
| Deadlock delta | 0 |
| Cache hit ratio | 99.6890% |
| Host CPU average | 8.0727% |
| Host memory average | 92.0727% |
| Telemetry samples | 11 |
| Telemetry errors | 0 |

## Bottleneck detected

Overall status: `ELEVATED`

The rules engine identified one high-severity finding:

**Potential memory pressure**

- Evidence: host memory averaged `92.0727%`
- Threshold: `85%`
- Recommended action: inspect host/container memory availability and PostgreSQL memory configuration
- Expected benefit: potential reduction in memory pressure
- Coverage status: `HIGH_EVIDENCE`
- Validation required: yes

This is a host-level memory observation. It is not a claim that PostgreSQL alone consumed 92% of memory.

## Findings not triggered

- CPU pressure was not triggered because average host CPU was `8.0727%`.
- Lock contention was not triggered because maximum lock waits were `0`.
- Connection pressure was not triggered because active connections were low.
- Poor cache behavior was not triggered because cache hit ratio was `99.6890%`.
- Tail-latency pressure was not triggered by the configured P95/average threshold.

## Query statistics

`pg_stat_statements` was unavailable or inaccessible. The engine continued with workload and PostgreSQL aggregate telemetry and emitted this warning:

```text
Query-level analysis unavailable because pg_stat_statements is not enabled or accessible.
```

No query-specific or candidate-index recommendation was generated. This avoids inventing query evidence.

## Output and testing

The JSON assessment completed successfully. CSV export was initially corrected to include the recommendation `description` field and then produced:

```text
artifacts/recommendations.csv
```

Final regression result:

```text
20 passed, 2 warnings
```

The warnings were non-failing FastAPI/Starlette deprecation warnings.

