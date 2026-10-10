from __future__ import annotations

import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BUNDLED = PROJECT_ROOT / "bundled"
ARTIFACTS = Path("artifacts")


def install_bundled(source: Path = BUNDLED, target: Path = ARTIFACTS) -> list[str]:
    """Copy the models and result files shipped with the project into the working artifacts folder.

    `artifacts/` is not in version control, so a fresh copy of the project has no trained models.
    The shipped ones are installed only where nothing exists: a model set trained on this machine
    is never mixed with, or replaced by, the shipped one. Returns the files that were copied.
    """
    if not source.is_dir():
        return []
    copied = []
    models = source / "models"
    if models.is_dir() and not any((target / "models").glob("*.joblib")):
        for file in sorted(models.iterdir()):
            if file.suffix in (".joblib", ".json"):
                (target / "models").mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, target / "models" / file.name)
                copied.append(f"models/{file.name}")
    for file in sorted(source.glob("*.json")):
        if not (target / file.name).exists():
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target / file.name)
            copied.append(file.name)
    return copied
