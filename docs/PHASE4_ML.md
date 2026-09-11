# Phase 4 ML Performance Prediction

Phase 4 uses measured Phase 3 experiments as ground-truth labels. The feature pipeline uses only pre-execution workload configuration: scenario, concurrency, target TPS, duration, burstiness, and operation-mix ratios. Measured latency, throughput, CPU, and lock metrics are targets, never predictors, preventing post-execution leakage.

Training uses grouped workload configurations so near-identical experiments do not appear in both training and test sets. Candidate models are Linear Regression, Random Forest, and Gradient Boosting. The best model for each target is selected by held-out MAE and persisted with its preprocessing pipeline and metadata using joblib.

The current database contains too few diverse measured experiments for defensible training. The pipeline therefore refuses to train with fewer than six usable experiments, fewer than four configurations, or fewer than two scenarios. No performance labels are fabricated. Run additional real workloads, for example across `NORMAL_DAY`, `SALARY_DAY`, and `HIGH_CONCURRENCY_TRANSFER`, before training.

Diagnose the current data:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python scripts/diagnose_ml_dataset.py
```

The database remains the source of truth; future CSV export can be derived from the same query. Prediction is exposed through `predict_performance(workload)` and warns when a scenario or numerical feature is outside the observed training range.
