from __future__ import annotations

"""Questions about the models that one cross-validated number does not answer.

How much data do they need, where are they weak, how much of the remaining error is noise,
and how much does the design of the experiments matter. Every function takes the usable
training frame and returns plain numbers; nothing here writes to the database or to disk.
"""

import numpy as np
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline

from .features import make_preprocessor
from .models import _estimator, build_model
from .train import MAX_FOLDS, baseline_predictions


def _folds(frame):
    folds = min(MAX_FOLDS, int(frame["load_key"].nunique()))
    return GroupKFold(n_splits=folds).split(frame, groups=frame["load_key"])


def learning_curve(frame, target: str, algorithm: str, sizes, repeats: int = 3, seed: int = 0) -> list[dict]:
    """Held-out error after training on only `size` runs, for each size.

    Load settings are held out exactly as in training. Within each fold the training runs are
    subsampled at random `repeats` times, so a point is the mean over folds and subsamples.
    """
    rng = np.random.default_rng(seed)
    splits = [(frame.iloc[train_index], frame.iloc[test_index]) for train_index, test_index in _folds(frame)]
    smallest = min(len(train) for train, _ in splits)
    # Folds leave slightly different numbers of runs to train on. Any size the smallest fold cannot
    # supply means "everything available", reported as one point at the mean number of runs used.
    everything = round(sum(len(train) for train, _ in splits) / len(splits))
    errors: dict[int, list[float]] = {}
    for train, test in splits:
        for size in sorted({int(size) if int(size) < smallest else everything for size in sizes}):
            whole = size == everything
            for _ in range(1 if whole else repeats):
                subset = train if whole else train.iloc[rng.choice(len(train), size=size, replace=False)]
                if subset["scenario"].nunique() < 2:
                    continue
                model = build_model(algorithm, target)
                model.fit(subset, subset[target].astype(float))
                errors.setdefault(size, []).append(float(mean_absolute_error(test[target].astype(float), model.predict(test))))
    return [{"runs": size, "mae": float(np.mean(values)), "mae_std": float(np.std(values)), "fits": len(values)} for size, values in sorted(errors.items())]


def out_of_fold(frame, target: str, algorithm: str):
    """Each run's prediction from a model that never saw its load setting, and the no-model answer."""
    predicted, baseline = np.zeros(len(frame)), np.zeros(len(frame))
    for train_index, test_index in _folds(frame):
        train, test = frame.iloc[train_index], frame.iloc[test_index]
        model = build_model(algorithm, target)
        model.fit(train, train[target].astype(float))
        predicted[test_index] = model.predict(test)
        baseline[test_index] = baseline_predictions(train, test, target)
    return predicted, baseline


def error_by_band(frame, target: str, algorithm: str, edges=(50, 150, 350)) -> list[dict]:
    """Held-out error split by requested rate: where the model is good and where it is not."""
    predicted, baseline = out_of_fold(frame, target, algorithm)
    actual = frame[target].astype(float).to_numpy()
    rate = frame["target_tps"].astype(float).to_numpy()
    bounds = [-np.inf, *edges, np.inf]
    bands = []
    for low, high in zip(bounds, bounds[1:]):
        inside = (rate >= low) & (rate < high)
        label = f"under {high:g} TPS" if low == -np.inf else f"{low:g} TPS and over" if high == np.inf else f"{low:g} to {high:g} TPS"
        if not inside.any():
            bands.append({"band": label, "runs": 0, "mae": None, "baseline_mae": None, "mean_actual": None})
            continue
        bands.append({
            "band": label,
            "runs": int(inside.sum()),
            "mae": float(np.abs(predicted[inside] - actual[inside]).mean()),
            "baseline_mae": float(np.abs(baseline[inside] - actual[inside]).mean()),
            "mean_actual": float(actual[inside].mean()),
        })
    return bands


def transfer(train, test, target: str, algorithm: str, rate_share: bool | None = None) -> dict:
    """Error on `test` of a model fitted on `train`: for example grid runs predicting random-load runs.

    `rate_share` forces throughput to be modelled as a share of the requested rate (True) or
    directly (False); None uses whatever training uses for the target.
    """
    if rate_share is None:
        model = build_model(algorithm, target)
    else:
        from .models import RateShare

        pipeline = Pipeline([("features", make_preprocessor().preprocessor), ("model", _estimator(algorithm))])
        model = RateShare(pipeline) if rate_share else pipeline
    model.fit(train, train[target].astype(float))
    actual = test[target].astype(float)
    return {
        "train_runs": len(train),
        "test_runs": len(test),
        "mae": float(mean_absolute_error(actual, model.predict(test))),
        "baseline_mae": float(mean_absolute_error(actual, baseline_predictions(train, test, target))),
    }


def noise_floor(frame, target: str) -> dict:
    """How much one configuration varies when it is simply run again."""
    groups = frame.groupby("configuration_key")[target]
    spread, mean = groups.std(ddof=1).dropna(), groups.mean()
    if spread.empty:
        return {"repeated_configurations": 0, "spread": None, "relative_spread_percent": None}
    relative = (spread / mean[spread.index]).replace([np.inf, -np.inf], np.nan).dropna()
    return {
        "repeated_configurations": int(len(spread)),
        "spread": float(spread.mean()),
        "relative_spread_percent": float(relative.mean() * 100) if len(relative) else None,
    }
