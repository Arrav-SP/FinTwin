from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline

from .features import make_preprocessor

ALGORITHMS = ("linear_regression", "random_forest", "gradient_boosting")


def _estimator(name: str):
    if name == "linear_regression":
        return LinearRegression()
    if name == "random_forest":
        return RandomForestRegressor(n_estimators=100, random_state=42)
    if name == "gradient_boosting":
        return GradientBoostingRegressor(random_state=42)
    raise ValueError(f"Unknown algorithm: {name}")


class RateShare(BaseEstimator, RegressorMixin):
    """Predict throughput as a share of the requested rate.

    Delivered throughput is the requested rate until the database saturates, then less.
    Learning the delivered share (near 1 below saturation) lets a model answer correctly for a
    requested rate it has never seen, where a tree fitted on raw throughput can only repeat
    the rates it was trained on.
    """

    def __init__(self, pipeline):
        self.pipeline = pipeline

    def fit(self, X, y):
        self.pipeline.fit(X, np.asarray(y, dtype=float) / X["target_tps"].astype(float).to_numpy())
        return self

    def predict(self, X):
        return self.pipeline.predict(X) * X["target_tps"].astype(float).to_numpy()


def build_model(name: str, target: str):
    """A fresh, unfitted model for one target: feature selection, then the named algorithm."""
    pipeline = Pipeline([("features", make_preprocessor().preprocessor), ("model", _estimator(name))])
    return RateShare(pipeline) if target == "actual_tps" else pipeline
