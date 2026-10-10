from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

LEARNING_SIZES = (15, 30, 60, 100, 140, 180, 1000)


def campaign_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {run["experiment_id"] for run in json.loads(path.read_text(encoding="utf-8"))["runs"] if "experiment_id" in run}


def main() -> None:
    import pandas as pd

    from backend.app.ml import study
    from backend.app.ml.dataset import TARGETS, load_experiments
    from backend.app.ml.registry import describe_models
    from backend.app.ml.train import training_rows

    parser = argparse.ArgumentParser(description="Study the stored models: learning curve, error by load, noise floor, and the effect of the experiment design.")
    parser.add_argument("--models", type=Path, default=Path("artifacts/models"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/study.json"))
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()

    models = {model["target"]: model for model in describe_models(args.models)}
    if set(models) != set(TARGETS):
        raise SystemExit("Train the models first: python scripts/train_models.py")
    trained_at = max(datetime.fromisoformat(model["trained_at"]) for model in models.values())

    frame, _ = load_experiments()
    usable = training_rows(frame)
    started = pd.to_datetime(usable["started_at"], utc=True)
    # The runs the stored models were fitted on, and the runs made afterwards (validation checks).
    seen, later = usable[started <= trained_at], usable[started > trained_at]
    ids = seen["experiment_id"].astype(str)
    grid, spread = seen[ids.isin(campaign_ids(Path("artifacts/campaign.json")))], seen[ids.isin(campaign_ids(Path("artifacts/campaign-random.json")))]

    report = {"trained_at": trained_at.isoformat(), "runs": len(seen), "load_settings": int(seen["load_key"].nunique()), "grid_runs": len(grid), "random_runs": len(spread), "runs_after_training": len(later), "targets": {}}
    for target in TARGETS:
        algorithm = models[target]["algorithm"]
        entry = {
            "algorithm": algorithm,
            "learning_curve": study.learning_curve(seen, target, algorithm, LEARNING_SIZES, repeats=args.repeats, seed=7),
            "error_by_band": study.error_by_band(seen, target, algorithm),
            "noise_floor": study.noise_floor(seen, target),
        }
        if len(grid) and len(spread):
            entry["grid_predicting_random"] = study.transfer(grid, spread, target, algorithm)
            entry["random_predicting_grid"] = study.transfer(spread, grid, target, algorithm)
        if len(later):
            entry["after_training"] = study.transfer(seen, later, target, algorithm)
        report["targets"][target] = entry
        print(f"{target}: done", flush=True)
    if len(grid) and len(spread):
        # The same algorithm on raw throughput, to show what modelling the delivered share buys.
        algorithm = models["actual_tps"]["algorithm"]
        report["throughput_modelling"] = {
            "raw": study.transfer(grid, spread, "actual_tps", algorithm, rate_share=False),
            "share_of_requested_rate": study.transfer(grid, spread, "actual_tps", algorithm, rate_share=True),
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Written to {args.output}")


if __name__ == "__main__":
    main()
