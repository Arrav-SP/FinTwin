# FinTwin Phase 5 — What-If Results

Phase 5 evaluated hypothetical workload changes using persisted Phase 4 models. These runs did not execute PostgreSQL workloads; all values are model predictions.

## Baseline and concurrency change

Baseline: `NORMAL_DAY`, concurrency `50`, target TPS `100`, duration `10` seconds.

Modified configuration: concurrency `100`, with all other parameters held constant.

| Predicted metric | Baseline | Modified | Absolute change | Percentage change |
|---|---:|---:|---:|---:|
| Average latency | 9.3317 ms | 9.3317 ms | 0.0000 ms | 0.00% |
| P95 latency | 16.6334 ms | 17.2626 ms | 0.6291 ms | 3.78% |
| Actual TPS | 103.3816 | 120.5949 | 17.2134 | 16.65% |
| Host CPU average | 22.2543% | 22.2543% | 0.0000 | 0.00% |
| Maximum lock wait count | 0 | 0 | 0 | Not defined from zero baseline |

Assessment: `MEDIUM_IMPACT`.

Warnings were generated because concurrency values `50` and `100` are outside the training range `4–12`, and target TPS `100` is outside the training range `10–30`.

## Multi-parameter change

Concurrency was changed from `50` to `100` and target TPS from `100` to `200`.

| Predicted metric | Baseline | Modified | Percentage change |
|---|---:|---:|---:|
| Average latency | 9.3317 ms | 9.3317 ms | 0.00% |
| P95 latency | 16.6334 ms | 20.4083 ms | 22.69% |
| Actual TPS | 103.3816 | 206.6617 | 99.90% |
| Host CPU average | 22.2543% | 22.2543% | 0.00% |

Assessment: `HIGH_IMPACT`. Both parameters were outside the observed training ranges, so this is extrapolative.

## Concurrency sensitivity sweep

Concurrency values tested: `25, 50, 75, 100`, with target TPS fixed at `100`.

| Concurrency | Predicted P95 | Predicted actual TPS |
|---:|---:|---:|
| 25 | 16.3189 ms | 94.7749 |
| 50 | 16.6334 ms | 103.3816 |
| 75 | 16.9480 ms | 111.9883 |
| 100 | 17.2626 ms | 120.5949 |

Model-derived sensitivity from the sweep:

- P95 latency: `0.01258 ms` per additional concurrent worker
- Actual TPS: `0.34427 TPS` per additional concurrent worker

## TPS sensitivity sweep

Target TPS values tested: `50, 100, 150, 200`, with concurrency fixed at `50`.

| Target TPS | Predicted P95 | Predicted actual TPS |
|---:|---:|---:|
| 50 | 15.0606 ms | 60.3482 |
| 100 | 16.6334 ms | 103.3816 |
| 150 | 18.2063 ms | 146.4150 |
| 200 | 19.7791 ms | 189.4484 |

Model-derived sensitivity from the sweep:

- P95 latency: `0.03146 ms` per additional target TPS
- Actual TPS: `0.86067 TPS` per additional target TPS

## Interpretation and limitations

What-if analysis shows how the trained model's predictions change when workload features are modified. It does not prove that changing a parameter will causally produce the same change in a real PostgreSQL system. All tested sweep values were outside the training ranges, so the warnings must be retained. The model was trained on only seven usable experiments; these results are suitable as a reproducible prototype demonstration, not as production capacity planning.

The final Phase 5 test run reported:

```text
17 passed, 2 warnings
```

