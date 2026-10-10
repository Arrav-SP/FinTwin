# FinTwin results (10 October 2026)

This file is the current statement of what was measured. The `PHASE*_RESULTS.md` files record earlier stages and are kept as history. The full account is in `FinTwin_Final_Project_Review_Report_v2.docx`.

Everything here comes from one development machine and from runs of eight seconds. The numbers describe this machine under these workloads.

## Sources

| File | Written by | Contents |
|---|---|---|
| `artifacts/campaign.json` | `scripts/run_campaign.py --design grid` | 140 runs: 7 scenarios x 5 load levels x 2 skews x 2 repetitions |
| `artifacts/campaign-random.json` | `scripts/run_campaign.py --design random` | 100 runs with workers 2-64 and rate 10-600 TPS drawn log-uniformly |
| `artifacts/models/*.json` | `scripts/train_models.py` | Per model: candidates, cross-validated error, baseline, noise floor, trained ranges |
| `artifacts/m3-validation.json` | 16 predict-then-run checks | Predicted, measured and baseline value per metric |
| `artifacts/study.json` | `scripts/run_study.py` | Learning curves, error by load band, noise floor, transfer between designs |

## Campaign

No run failed. Two runs of the random campaign were interrupted when the machine slept (31 minutes and 8 hours elapsed for an 8-second run); they are flagged and excluded.

| Workers | Requested TPS | Delivered TPS | Average latency (ms) | P95 latency (ms) | Runs with a lock wait |
|---|---|---|---|---|---|
| 4 | 20 | 20.1 | 12.3 | 38.5 | 0 of 28 |
| 8 | 60 | 60.0 | 7.6 | 11.9 | 0 of 28 |
| 16 | 150 | 149.8 | 6.3 | 10.1 | 1 of 28 |
| 32 | 300 | 299.3 | 6.9 | 12.4 | 4 of 28 |
| 48 | 600 | 488.3 | 67.0 | 188.0 | 21 of 28 |

- The database holds 280 completed runs and 383,385 operations. 2,176 operations failed, all rejected for insufficient balance. No deadlock was reported in any run.
- At 600 TPS, 24 of 28 runs delivered under 90% of the requested rate.
- Skew turns saturation into contention: for HIGH_CONCURRENCY_TRANSFER at the top level, waiting lock requests peaked at 1.5 on average without skew and 43 with skew 1.2, and P95 latency went from 118 ms to 702 ms.
- The lightest level is slower than the next two. The cause was not investigated.

## Models

Trained on 247 runs (176 configurations, 109 load settings). Error is the mean absolute error from 5-fold cross-validation with whole load settings held out. "No model" predicts the requested rate for throughput and the scenario's mean otherwise.

| Metric | Chosen model | Error | No model | Between identical runs | R² |
|---|---|---|---|---|---|
| Average latency (ms) | Random forest | 3.42 | 15.22 | 1.01 | 0.82 |
| P95 latency (ms) | Random forest | 23.87 | 48.39 | 5.10 | 0.42 |
| Throughput (TPS) | Random forest on share of requested rate | 6.63 | 15.45 | 3.32 | 0.98 |
| Host CPU (%) | Linear regression | 5.80 | 13.48 | 2.35 | 0.67 |
| Lock waits | Random forest | 2.04 | 4.39 | 0.38 | 0.52 |

## Validation: 16 workloads predicted, then run

| Metric | Model error | No-model error | Model closer in |
|---|---|---|---|
| Average latency (ms) | 3.67 | 9.54 | 13 of 16 |
| P95 latency (ms) | 13.99 | 24.40 | 12 of 16 |
| Throughput (TPS) | 5.10 | 9.71 | 9 of 16 |
| Host CPU (%) | 3.75 | 10.46 | 14 of 16 |
| Lock waits | 0.97 | 2.19 | 14 of 16 |

The errors match the cross-validated estimates. For throughput the model wins on average but in only 9 of 16 cases, because below saturation the requested rate is already nearly exact.

## Study

- **Data needed.** Error falls quickly up to about 100 runs and little after: average latency 4.2 ms at 100 runs and 3.4 ms at 198.
- **Where the error is.** Below 350 TPS (210 runs) average-latency error is at most 2.3 ms and throughput error at most 1.8 TPS. At 350 TPS and above (37 runs) they are 15.0 ms and 40.3 TPS, and for P95 latency and lock waits the model is barely better than no model.
- **Noise.** Identical runs differ by 6.4% of the mean for average latency, 11.1% for P95 latency, 9.0% for host CPU and 0.7% for throughput.
- **Experiment design.** A random forest fitted on raw throughput from the five-level grid has an error of 74.0 TPS on the random-load runs. Modelled as a share of the requested rate it is 4.8 TPS, against 5.4 for no model.

## An evaluation that was wrong

Models trained on the grid campaign alone, cross-validated with whole configurations held out, looked accurate (throughput error 4.1 TPS against a baseline of 22.6). Four validation runs at loads between the grid levels showed throughput 25% to 40% too low: for 100 TPS requested the model predicted 60. Other scenarios at the same load had stayed in the training folds, so the models were never asked to interpolate. The fixes were to hold out whole load settings, to model throughput as a share of the requested rate, and to add the random-load campaign.

## Limits

- One machine; host CPU and memory are machine-wide.
- Runs of 8 to 10 seconds. Burstiness was 0 in every run.
- Weak above about 350 TPS. No confidence interval on a prediction.
- Latency is service time; queue wait is recorded but not predicted.
- Lock waits are sampled once a second and undercount short waits.
- No automated test runs opposing transfers concurrently; the absence of deadlocks is an observation.
