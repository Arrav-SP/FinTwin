from __future__ import annotations

import json
from pathlib import Path
from sqlalchemy import text

from ..database import engine
from .dataset import TARGETS, load_experiments, quality_report

MAX_FOLDS = 5


def diagnose() -> dict:
    with engine.connect() as connection:
        total = connection.execute(text("SELECT COUNT(*) FROM experiment_runs")).scalar_one()
        completed = connection.execute(text("SELECT COUNT(*) FROM experiment_runs WHERE status = 'COMPLETED'")).scalar_one()
        summaries = connection.execute(text("SELECT COUNT(*) FROM experiment_summaries")).scalar_one()
        samples = connection.execute(text("SELECT COUNT(*) FROM telemetry_samples")).scalar_one()
        scenarios = connection.execute(text("SELECT COUNT(DISTINCT scenario) FROM experiment_runs WHERE status = 'COMPLETED'")).scalar_one()
        configs = connection.execute(text("SELECT COUNT(DISTINCT configuration::text) FROM experiment_runs WHERE status = 'COMPLETED'")).scalar_one()
    return {"total_experiments": total, "completed_experiments": completed, "usable_experiments": summaries, "unique_configurations": configs, "unique_scenarios": scenarios, "telemetry_samples": samples, "missing_targets": {}, "target_columns": TARGETS}


def training_rows(frame):
    """Completed, uninterrupted runs timed by the current runner, with every target measured."""
    if frame.empty:
        return frame
    rows = frame[(frame["status"] == "COMPLETED") & frame["current_timing"] & ~frame["interrupted"]]
    return rows.dropna(subset=[target for target in TARGETS if target in rows])


def baseline_predictions(train, test, target):
    """What you would predict without a model.

    Throughput: the rate that was asked for. Anything else: the mean of that scenario's
    training runs, or the overall mean for a scenario the training rows do not contain.
    """
    if target == "actual_tps":
        return test["target_tps"].astype(float).to_numpy()
    by_scenario = train.groupby("scenario")[target].mean()
    return test["scenario"].map(by_scenario).fillna(train[target].mean()).astype(float).to_numpy()


def repeat_spread(frame, target):
    """Mean standard deviation between runs of an identical configuration: the noise a model cannot beat."""
    spread = frame.groupby("configuration_key")[target].std(ddof=1).dropna()
    return float(spread.mean()) if len(spread) else None


def _scores(actual, predicted) -> dict:
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    varied = float(actual.max()) != float(actual.min())
    return {"mae": float(mean_absolute_error(actual, predicted)), "rmse": float(mean_squared_error(actual, predicted) ** 0.5), "r2": float(r2_score(actual, predicted)) if varied else None}


def cross_validate(usable, target, folds: int) -> dict:
    """Out-of-fold error of every candidate and of the baseline, with whole load settings held out.

    Every run that shares a number of workers and a requested rate goes into the same fold, so a
    model is always scored at a load it was not trained on. Holding out only whole configurations
    is not enough: other scenarios at the same load stay in training, and a tree model then looks
    accurate while being unable to answer for a load between the ones it has seen.
    """
    import numpy as np
    from sklearn.model_selection import GroupKFold
    from .models import ALGORITHMS, build_model

    actual = usable[target].astype(float).to_numpy()
    predicted = {name: np.zeros(len(usable)) for name in ALGORITHMS}
    baseline = np.zeros(len(usable))
    for train_index, test_index in GroupKFold(n_splits=folds).split(usable, groups=usable["load_key"]):
        train, test = usable.iloc[train_index], usable.iloc[test_index]
        baseline[test_index] = baseline_predictions(train, test, target)
        for name in ALGORITHMS:
            model = build_model(name, target)
            model.fit(train, train[target].astype(float))
            predicted[name][test_index] = model.predict(test)
    return {"candidates": {name: _scores(actual, values) for name, values in predicted.items()}, "baseline": _scores(actual, baseline)}


def train_models(output_dir: Path = Path("artifacts/models")) -> dict:
    import joblib
    from .features import make_preprocessor
    from .models import build_model

    frame, telemetry_count = load_experiments()
    usable = training_rows(frame)
    configurations = int(usable["configuration_key"].nunique()) if not usable.empty else 0
    scenarios = int(usable["scenario"].nunique()) if not usable.empty else 0
    if len(usable) < 6 or configurations < 4 or scenarios < 2:
        raise ValueError(f"Insufficient measured data for defensible ML evaluation: {len(usable)} usable runs, {configurations} configurations, {scenarios} scenarios ({quality_report(frame, telemetry_count)})")
    folds = min(MAX_FOLDS, int(usable["load_key"].nunique()))
    if folds < 2:
        raise ValueError("Insufficient measured data for defensible ML evaluation: every run uses the same load setting")
    features = make_preprocessor()
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for target in TARGETS:
        evaluation = cross_validate(usable, target, folds)
        name = min(evaluation["candidates"], key=lambda candidate: evaluation["candidates"][candidate]["mae"])
        # The chosen algorithm is refitted on every usable run; the error above is its cross-validated estimate.
        pipeline = build_model(name, target)
        pipeline.fit(usable, usable[target].astype(float))
        joblib.dump(pipeline, output_dir / f"{target}.joblib")
        metadata = {
            "target": target,
            "algorithm": name,
            "training_samples": len(usable),
            "test_samples": len(usable),
            "configurations": configurations,
            "cv_folds": folds,
            "held_out": "load settings",
            "feature_columns": features.feature_columns,
            "metrics": evaluation["candidates"][name],
            "candidates": evaluation["candidates"],
            "baseline": evaluation["baseline"],
            "repeat_spread": repeat_spread(usable, target),
            "scenario_values": sorted(usable["scenario"].unique().tolist()),
            "numeric_ranges": {column: [float(usable[column].min()), float(usable[column].max())] for column in features.feature_columns if column != "scenario"},
        }
        (output_dir / f"{target}.json").write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
        results[target] = metadata
    return results


if __name__ == "__main__":
    print(json.dumps(diagnose(), indent=2, default=str))
