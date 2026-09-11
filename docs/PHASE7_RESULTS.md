# Phase 7 — Measured Validation Results

## Validation run

This result was produced by executing the Phase 7 validation workflow against the real PostgreSQL database. The prediction was generated first, then the identical workload configuration was executed through the Phase 2 workload runner with Phase 3 telemetry enabled.

| Field | Measured value |
|---|---|
| Validation ID | `5806a7d1-14b7-49d5-85e9-33155407f50e` |
| Actual experiment ID | `5e1cc15d-bb89-48e2-96fa-235f934f28c6` |
| Scenario | `NORMAL_DAY` |
| Concurrency | 10 |
| Target TPS | 10 |
| Duration | 10 seconds |
| Seed | 42 |
| Validation status | `COMPLETED` |
| Model warnings | None |

## Predicted versus actual performance

| Metric | Predicted | Actual | Absolute error | Percentage error |
|---|---:|---:|---:|---:|
| Average latency | 9.4634 ms | 18.8324 ms | 9.3690 ms | 49.7494% |
| P95 latency | 13.2990 ms | 39.7268 ms | 26.4278 ms | 66.5239% |
| Throughput | 12.1508 TPS | 10.0779 TPS | 2.0729 TPS | 20.5683% |
| Host CPU average | 13.1292% | 26.5455% | 13.4163 percentage points | 50.5408% |
| Maximum lock waits | 0 | 0 | 0 | Not applicable because actual value was zero |

## Interpretation

The prediction successfully matched to a real PostgreSQL experiment and produced a complete validation record. The model predicted the direction and approximate scale of the workload, but this single run shows meaningful underprediction:

- Average latency was approximately 49.75% higher than predicted.
- P95 latency was approximately 66.52% higher than predicted.
- Actual throughput was approximately 20.57% below predicted throughput.
- Actual host CPU was approximately 50.54% higher than predicted.
- Lock-wait behavior matched exactly at zero observed waits.

The largest discrepancy was P95 latency, indicating that tail behavior was not captured accurately for this configuration. This is evidence of model error, not a reason to adjust the measured values.

## Research integrity and limitations

All actual values came from the real PostgreSQL workload experiment `5e1cc15d-bb89-48e2-96fa-235f934f28c6` and its Phase 3 telemetry summary. No predicted values were reused as actual values, and no synthetic performance labels were created.

This is one validation configuration and is not statistically sufficient to claim general model accuracy. Additional real experiments are required across unseen scenarios, concurrency levels, TPS levels, and repeated runs. The benchmark CSV should be analyzed separately once its contents are available.

## Reproduction

```powershell
$env:PYTHONPATH = (Get-Location).Path
python scripts\initialize_database.py
python scripts\validate_prediction.py `
  --scenario NORMAL_DAY `
  --concurrency 10 `
  --target-tps 10 `
  --duration 10 `
  --output artifacts\validation.json
```

The persisted record can be checked with:

```powershell
docker exec fintwin-postgres psql -U fintwin -d fintwin -c "SELECT validation_id, scenario, validation_status, actual_experiment_id, error_message FROM validation_experiments ORDER BY created_at DESC;"
```
