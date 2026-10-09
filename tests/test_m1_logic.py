import random
import statistics
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from backend.app import what_if
from backend.app.database import engine
from backend.app.main import app
from backend.app.telemetry.metrics import average_excluding_initial
from backend.app.validation import summarize_validations
from backend.app.workload import runner as runner_module
from backend.app.workload.config import MAX_CONCURRENCY, Scenario, WorkloadConfig
from backend.app.workload.runner import WorkloadRunner


def test_what_if_applies_default_duration_when_missing():
    result = what_if.normalize_workload({"scenario": "NORMAL_DAY", "concurrency": 5, "target_tps": 10})
    assert result["duration_seconds"] == 10.0


def test_host_cpu_average_ignores_initial_sample():
    rows = [
        {"sample_kind": "INITIAL", "host_cpu_percent": 0.0},
        {"sample_kind": "SAMPLE", "host_cpu_percent": 20.0},
        {"sample_kind": "FINAL", "host_cpu_percent": 40.0},
    ]
    assert average_excluding_initial(rows, "host_cpu_percent") == 30.0
    assert average_excluding_initial([rows[0]], "host_cpu_percent") is None


def _validation(concurrency, predicted, actual):
    return {"validation_status": "COMPLETED", "scenario": "NORMAL_DAY", "workload_configuration": {"concurrency": concurrency, "target_tps": 10, "duration_seconds": 10}, "predicted_metrics": {"predicted_actual_tps": predicted}, "actual_metrics": {"actual_tps": actual}, "error_metrics": {}}


def test_r2_is_withheld_when_all_validations_share_one_configuration():
    records = [_validation(10, 12.0, 10.07), _validation(10, 12.0, 10.08), _validation(10, 12.0, 10.09)]
    overall = summarize_validations(records)["overall"]["actual_tps"]
    assert overall["r2"] is None
    assert overall["mae"] == pytest.approx(1.92)


def test_r2_is_reported_across_distinct_configurations():
    records = [_validation(10, 11.0, 10.0), _validation(20, 19.0, 20.0)]
    assert summarize_validations(records)["overall"]["actual_tps"]["r2"] == pytest.approx(0.96)


def test_account_selection_uses_ids_loaded_once_per_run(monkeypatch):
    class NoDatabase:
        def connect(self):
            raise AssertionError("account selection must not query the database per operation")

    monkeypatch.setattr(runner_module, "engine", NoDatabase())
    runner = WorkloadRunner(WorkloadConfig())
    runner._set_account_ids([11, 12, 13, 14])
    source, destination = runner._account_pair(random.Random(1))
    assert source != destination and {source, destination} <= {11, 12, 13, 14}


def _selection_share(skew):
    runner = WorkloadRunner(WorkloadConfig(account_skew=skew))
    runner._set_account_ids(list(range(1, 101)))
    rng = random.Random(7)
    counts = Counter(runner._account_pair(rng)[0] for _ in range(4000))
    account, hits = counts.most_common(1)[0]
    return account, hits / 4000


def test_uniform_selection_has_no_hot_account():
    assert _selection_share(0.0)[1] < 0.03


def test_skewed_selection_concentrates_on_the_first_accounts():
    account, share = _selection_share(1.2)
    assert account == 1 and share > 0.10


def test_account_skew_must_not_be_negative():
    with pytest.raises(ValueError):
        WorkloadConfig(account_skew=-0.5)


def test_arrivals_are_evenly_spaced_without_burstiness():
    offsets = WorkloadRunner(WorkloadConfig(target_tps=10, duration_seconds=2))._arrival_offsets(20)
    assert offsets == pytest.approx([index / 10 for index in range(20)])


def test_burstiness_varies_gaps_but_keeps_the_mean_rate():
    runner = WorkloadRunner(WorkloadConfig(target_tps=10, duration_seconds=200, burstiness=1.0))
    offsets = runner._arrival_offsets(2000)
    gaps = [later - earlier for earlier, later in zip(offsets, offsets[1:])]
    assert statistics.pstdev(gaps) > 0.05
    assert statistics.mean(gaps) == pytest.approx(0.1, rel=0.1)
    assert offsets == WorkloadRunner(WorkloadConfig(target_tps=10, duration_seconds=200, burstiness=1.0))._arrival_offsets(2000)


def test_concurrency_above_the_supported_maximum_is_rejected():
    WorkloadConfig(concurrency=MAX_CONCURRENCY)
    with pytest.raises(ValueError, match="concurrency"):
        WorkloadConfig(concurrency=MAX_CONCURRENCY + 1)


def test_connection_pool_can_serve_the_maximum_concurrency():
    assert engine.pool.size() + engine.pool._max_overflow >= MAX_CONCURRENCY + 4


@pytest.mark.parametrize("payload", [{"concurrency": MAX_CONCURRENCY + 1}, {"duration_seconds": 100000}, {"target_tps": 1000000}])
def test_validation_endpoint_rejects_out_of_bounds_requests(payload):
    response = TestClient(app).post("/api/validation", json={"scenario": Scenario.NORMAL_DAY.value, **payload})
    assert response.status_code == 422
