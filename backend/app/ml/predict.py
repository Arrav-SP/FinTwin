from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd

from .dataset import RATIOS, TARGETS
from ..workload.config import DEFAULT_MIXES, Scenario


# Loaded models, keyed by file and its modification time: unpickling a forest for every prediction is
# slow, and on a small host it dominates the request.
_loaded: dict[Path, tuple[float, object, dict]] = {}


def forget_loaded_models() -> None:
    _loaded.clear()


def _load(artifact: Path, metadata_path: Path) -> tuple[object, dict]:
    stamp = artifact.stat().st_mtime
    cached = _loaded.get(artifact)
    if cached is None or cached[0] != stamp:
        cached = (stamp, joblib.load(artifact), json.loads(metadata_path.read_text(encoding="utf-8")))
        _loaded[artifact] = cached
    return cached[1], cached[2]


def warm(model_dir: Path = Path("artifacts/models")) -> None:
    """Load every model now, so the first visitor does not wait for it."""
    for target in TARGETS:
        artifact, metadata_path = model_dir / f"{target}.joblib", model_dir / f"{target}.json"
        if artifact.exists() and metadata_path.exists():
            _load(artifact, metadata_path)


def predict_performance(workload: dict, model_dir: Path = Path("artifacts/models")) -> dict:
    if not model_dir.exists() or not any(model_dir.glob("*.joblib")):
        raise FileNotFoundError("No trained model artifacts exist. Run additional measured experiments before training.")
    row = {"scenario": workload["scenario"], "concurrency": workload["concurrency"], "target_tps": workload["target_tps"], "duration_seconds": workload.get("duration_seconds", 10.0), "burstiness": workload.get("burstiness", 0.0), "account_skew": workload.get("account_skew", 0.0)}
    mix = workload.get("operation_mix") or DEFAULT_MIXES.get(Scenario(workload["scenario"]), {})
    for operation in RATIOS:
        row[f"{operation.lower()}_ratio"] = mix.get(operation, 0.0)
    frame = pd.DataFrame([row])
    predictions, warnings = {}, []
    for target in TARGETS:
        artifact = model_dir / f"{target}.joblib"
        metadata_path = model_dir / f"{target}.json"
        if not artifact.exists() or not metadata_path.exists():
            continue
        model, metadata = _load(artifact, metadata_path)
        predictions[f"predicted_{target}"] = float(model.predict(frame)[0])
        if row["scenario"] not in metadata["scenario_values"]:
            warnings.append(f"Scenario {row['scenario']} was not observed during training")
        for feature, bounds in metadata["numeric_ranges"].items():
            if row.get(feature, 0) < bounds[0] or row.get(feature, 0) > bounds[1]:
                warnings.append(f"{feature}={row.get(feature)} is outside the training range {bounds[0]}–{bounds[1]}")
    if not predictions:
        raise FileNotFoundError("No complete trained model set is available")
    return {"predictions": predictions, "warnings": sorted(set(warnings))}
