from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd

from .dataset import RATIOS, TARGETS


def predict_performance(workload: dict, model_dir: Path = Path("artifacts/models")) -> dict:
    if not model_dir.exists() or not any(model_dir.glob("*.joblib")):
        raise FileNotFoundError("No trained model artifacts exist. Run additional measured experiments before training.")
    row = {"scenario": workload["scenario"], "concurrency": workload["concurrency"], "target_tps": workload["target_tps"], "duration_seconds": workload.get("duration_seconds", 10.0), "burstiness": workload.get("burstiness", 0.0)}
    mix = workload.get("operation_mix", {})
    for operation in RATIOS:
        row[f"{operation.lower()}_ratio"] = mix.get(operation, 0.0)
    frame = pd.DataFrame([row])
    predictions, warnings = {}, []
    for target in TARGETS:
        artifact = model_dir / f"{target}.joblib"
        metadata_path = model_dir / f"{target}.json"
        if not artifact.exists() or not metadata_path.exists():
            continue
        model = joblib.load(artifact)
        metadata = __import__("json").loads(metadata_path.read_text(encoding="utf-8"))
        predictions[f"predicted_{target}"] = float(model.predict(frame)[0])
        if row["scenario"] not in metadata["scenario_values"]:
            warnings.append(f"Scenario {row['scenario']} was not observed during training")
        for feature, bounds in metadata["numeric_ranges"].items():
            if row.get(feature, 0) < bounds[0] or row.get(feature, 0) > bounds[1]:
                warnings.append(f"{feature}={row.get(feature)} is outside the training range {bounds[0]}–{bounds[1]}")
    if not predictions:
        raise FileNotFoundError("No complete trained model set is available")
    return {"predictions": predictions, "warnings": sorted(set(warnings))}
