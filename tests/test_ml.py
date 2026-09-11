import pytest

pytest.importorskip("sklearn")

from backend.app.ml.features import NUMERIC_FEATURES, make_preprocessor


def test_feature_schema_is_stable_and_pre_execution_only():
    features = make_preprocessor()
    assert "target_tps" in features.feature_columns
    assert "average_latency_ms" not in features.feature_columns
    assert "host_cpu_avg_percent" not in features.feature_columns
    assert NUMERIC_FEATURES[-1] == "loan_processing_ratio"


def test_prediction_is_blocked_without_measured_models(tmp_path):
    from backend.app.ml.predict import predict_performance
    with pytest.raises(FileNotFoundError):
        predict_performance({"scenario": "NORMAL_DAY"}, tmp_path)
