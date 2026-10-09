from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .dataset import TARGETS


def describe_models(model_dir: Path = Path("artifacts/models")) -> list[dict]:
    """What is known about each stored model: algorithm, held-out error, and the range it was trained on."""
    if not model_dir.exists():
        return []
    models = []
    for target in TARGETS:
        metadata_path, artifact = model_dir / f"{target}.json", model_dir / f"{target}.joblib"
        if not metadata_path.exists() or not artifact.exists():
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["trained_at"] = datetime.fromtimestamp(artifact.stat().st_mtime, timezone.utc).isoformat()
        models.append(metadata)
    return models
