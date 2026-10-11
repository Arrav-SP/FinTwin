from __future__ import annotations

"""Retraining the models on runs made on a public server.

The shipped models describe the machine the reference runs were recorded on. A public server is
a different machine, so once enough runs have been made there the models are trained again on
those runs alone, from every signed-in person, and again after each further batch.
"""

import json
import shutil
from pathlib import Path

from sqlalchemy import text

from ..config import get_settings
from ..database import engine

MODELS = Path("artifacts/models")


def site_runs() -> int:
    """Completed runs made by signed-in people. A cheap count; training applies its own stricter selection."""
    with engine.connect() as connection:
        return connection.execute(text("SELECT COUNT(*) FROM experiment_runs WHERE started_by IS NOT NULL AND status = 'COMPLETED'")).scalar_one()


def trained_at_runs(directory: Path = MODELS) -> int | None:
    """How many site runs existed when the current models were trained on the site; None if they never were."""
    for path in sorted(directory.glob("*.json")):
        metadata = json.loads(path.read_text(encoding="utf-8"))
        if metadata.get("trained_on") == "site":
            return int(metadata.get("site_runs_at_training", 0))
    return None


def due(site_runs: int, trained_at_runs: int | None, minimum: int | None = None, every: int | None = None) -> bool:
    settings = get_settings()
    minimum = settings.site_min_runs if minimum is None else minimum
    every = settings.retrain_every if every is None else every
    if site_runs < minimum:
        return False
    return trained_at_runs is None or site_runs - trained_at_runs >= every


def _current_site_runs() -> int:
    return globals()["site_runs"]()  # the parameter below has the same name as the function


def retrain(directory: Path = MODELS, site_runs: int | None = None) -> dict:
    """Train on site runs into a side folder, and swap the result in only if the whole set was produced."""
    from .. import archive
    from . import predict
    from .train import train_models

    staging = directory.with_name(directory.name + ".new")
    shutil.rmtree(staging, ignore_errors=True)
    try:
        results = train_models(staging, site_only=True)
        count = site_runs if site_runs is not None else _current_site_runs()
        for path in staging.glob("*.json"):
            metadata = json.loads(path.read_text(encoding="utf-8"))
            metadata["site_runs_at_training"] = count
            path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
        directory.mkdir(parents=True, exist_ok=True)
        for path in sorted(staging.iterdir()):
            path.replace(directory / path.name)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    predict.forget_loaded_models()
    archive.save_models(directory)
    first = next(iter(results.values()))
    return {"trained_on": first["trained_on"], "training_samples": first["training_samples"], "site_runs_at_training": count}
