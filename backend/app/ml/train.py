from __future__ import annotations

import json
from pathlib import Path

import joblib
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline

from .dataset import TARGETS, load_experiments, quality_report
from .features import make_preprocessor


def diagnose() -> dict:
    frame, telemetry_count = load_experiments()
    report = quality_report(frame, telemetry_count)
    return {"total_experiments": report.total_experiments, "completed_experiments": report.completed_experiments, "usable_experiments": report.usable_experiments, "unique_configurations": report.unique_configurations, "unique_scenarios": report.unique_scenarios, "telemetry_samples": report.telemetry_samples, "missing_targets": report.missing_targets, "target_columns": TARGETS}


def train_models(output_dir: Path = Path("artifacts/models")) -> dict:
    frame, telemetry_count = load_experiments()
    report = quality_report(frame, telemetry_count)
    if report.usable_experiments < 6 or report.unique_configurations < 4 or report.unique_scenarios < 2:
        raise ValueError(f"Insufficient measured data for defensible ML evaluation: {report}")
    usable = frame[frame["status"] == "COMPLETED"].dropna(subset=[target for target in TARGETS if target in frame])
    features = make_preprocessor()
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
    train_idx, test_idx = next(splitter.split(usable, groups=usable["configuration_key"]))
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    models = {"linear_regression": LinearRegression(), "random_forest": RandomForestRegressor(n_estimators=100, random_state=42), "gradient_boosting": GradientBoostingRegressor(random_state=42)}
    for target in TARGETS:
        if usable[target].isna().any():
            continue
        best = None
        for name, estimator in models.items():
            pipeline = Pipeline([("features", features.preprocessor), ("model", estimator)])
            pipeline.fit(usable.iloc[train_idx], usable.iloc[train_idx][target])
            predicted = pipeline.predict(usable.iloc[test_idx])
            metrics = {"mae": mean_absolute_error(usable.iloc[test_idx][target], predicted), "rmse": mean_squared_error(usable.iloc[test_idx][target], predicted) ** 0.5, "r2": r2_score(usable.iloc[test_idx][target], predicted)}
            candidate = (metrics["mae"], name, pipeline, metrics)
            if best is None or candidate[0] < best[0]:
                best = candidate
        _, name, pipeline, metrics = best
        joblib.dump(pipeline, output_dir / f"{target}.joblib")
        metadata = {"target": target, "algorithm": name, "training_samples": len(train_idx), "test_samples": len(test_idx), "feature_columns": features.feature_columns, "metrics": metrics, "scenario_values": sorted(usable["scenario"].unique().tolist()), "numeric_ranges": {column: [float(usable[column].min()), float(usable[column].max())] for column in features.feature_columns if column != "scenario"}}
        (output_dir / f"{target}.json").write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
        results[target] = metadata
    return results


if __name__ == "__main__":
    print(json.dumps(diagnose(), indent=2, default=str))
