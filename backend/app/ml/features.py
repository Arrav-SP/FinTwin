from __future__ import annotations

from dataclasses import dataclass
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder

from .dataset import RATIOS

NUMERIC_FEATURES = ("concurrency", "target_tps", "duration_seconds", "burstiness", *[f"{operation.lower()}_ratio" for operation in RATIOS])


@dataclass(frozen=True)
class FeatureSet:
    preprocessor: ColumnTransformer
    feature_columns: tuple[str, ...]


def make_preprocessor() -> FeatureSet:
    preprocessor = ColumnTransformer([("scenario", OneHotEncoder(handle_unknown="ignore"), ["scenario"]), ("numeric", "passthrough", list(NUMERIC_FEATURES))], remainder="drop")
    return FeatureSet(preprocessor, ("scenario", *NUMERIC_FEATURES))

