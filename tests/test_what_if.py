import pytest
from backend.app import what_if

@pytest.fixture
def fake_predict(monkeypatch):
    def predict(config):
        return {"predictions": {"predicted_average_latency_ms": float(config["concurrency"] + config["target_tps"] / 10), "predicted_actual_tps": float(config["target_tps"])}, "warnings": ["outside range"] if config["concurrency"] > 100 else []}
    monkeypatch.setattr(what_if, "predict_performance", predict)

def baseline():
    return {"scenario": "NORMAL_DAY", "concurrency": 50, "target_tps": 100, "duration_seconds": 10}

def test_single_and_multi_parameter_changes(fake_predict):
    result = what_if.compare_workloads(baseline(), {**baseline(), "concurrency": 100, "target_tps": 200})
    assert result["modified"]["duration_seconds"] == 10
    assert "predicted_average_latency_ms" in result["deltas"]

def test_sweep_and_sensitivity(fake_predict):
    result = what_if.sensitivity_analysis(baseline(), "concurrency", [25, 50, 75, 100])
    assert len(result["results"]) == 4
    assert "predicted_average_latency_ms" in result["model_derived_sensitivity"]

def test_invalid_mix_and_duplicate_sweep(fake_predict):
    with pytest.raises(ValueError):
        what_if.normalize_workload({**baseline(), "operation_mix": {"TRANSFER": 0.5}})
    with pytest.raises(ValueError):
        what_if.sweep_workload(baseline(), "concurrency", [25, 25])

def test_warnings_are_preserved(fake_predict):
    result = what_if.compare_workloads(baseline(), {**baseline(), "concurrency": 200})
    assert "outside range" in result["warnings"]
