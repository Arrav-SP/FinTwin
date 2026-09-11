# FinTwin Phase 4 — Measured Results

This document records the actual Phase 4 run results. Values below came from real PostgreSQL workload executions and held-out model evaluation; no performance labels were fabricated.

## Dataset diagnostics

Recorded after running six additional workloads:

| Metric | Value |
|---|---:|
| Total experiments | 8 |
| Completed experiments | 8 |
| Usable experiment summaries | 7 |
| Unique workload configurations | 7 |
| Unique scenarios | 5 |
| Telemetry samples | 77 |

The dataset is sufficient for a preliminary training run, but remains small for statistically strong conclusions.

## Training configuration

- Training samples: 5
- Held-out test samples: 2
- Split strategy: grouped by workload configuration
- Input features: scenario, concurrency, target TPS, duration, burstiness, and operation-mix ratios
- Post-execution metrics were excluded from input features to prevent leakage.

## Model evaluation

| Target | Selected model | MAE | RMSE | R² |
|---|---|---:|---:|---:|
| Average latency | Gradient Boosting | 2.5156 ms | 2.7334 ms | -0.1886 |
| P95 latency | Linear Regression | 1.0362 ms | 1.1315 ms | 0.2651 |
| Actual TPS | Linear Regression | 0.3546 TPS | 0.4954 TPS | 0.9956 |
| Host CPU average | Gradient Boosting | 2.6601 percentage points | 3.3761 percentage points | 0.5935 |
| Maximum lock wait count | Linear Regression | 0 | 0 | 1.0000 |

The lock-wait result is not substantively meaningful because all observed experiments had zero lock waits. The negative average-latency R² indicates that the current sample is too small and variable for reliable latency prediction. These are reported honestly as preliminary results.

## Prediction demonstration

Hypothetical workload:

- Scenario: `FESTIVAL_SPIKE`
- Concurrency: 8
- Target TPS: 20
- Duration: 10 seconds

Predictions from the persisted models before executing that hypothetical workload:

| Metric | Prediction |
|---|---:|
| Average latency | 10.4248 ms |
| P95 latency | 13.6403 ms |
| Actual TPS | 20.0645 TPS |
| Host CPU average | 15.0405% |
| Maximum lock wait count | 0 |

The first prediction invocation warned about missing operation ratios because the CLI did not apply the scenario default mix. The prediction interface was then corrected to use the existing Phase 2 scenario mix automatically.

## Validation

The final Phase 4 test run reported:

```text
13 passed, 2 warnings
```

The warnings were FastAPI/Starlette deprecation warnings and did not indicate test failures.

## Limitations and next experiments

The training set is hardware-specific, synthetic, and small. More repeated runs across varied concurrency, target TPS, durations, operation mixes, and scenarios are required before claiming robust generalization. Future experiments should especially include non-zero lock contention and a wider range of workload sizes. Model artifacts are local generated outputs and are intentionally excluded from Git.

