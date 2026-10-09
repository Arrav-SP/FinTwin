import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from backend.app import what_if
from backend.app.jobs import JobManager
from backend.app.limits import MAX_CONCURRENCY
from backend.app.main import app
from backend.app.ml.registry import describe_models
from backend.app.telemetry.metrics import latency_breakdown
from backend.app.workload.config import DEFAULT_MIXES, Scenario


def wait_for(condition, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return False


# ---------------------------------------------------------------- background jobs

def test_job_reports_its_result_when_the_work_finishes():
    manager = JobManager()
    job = manager.submit("workload", {"scenario": "NORMAL_DAY"}, lambda: {"experiment_id": "abc"})
    assert job["status"] in ("queued", "running", "completed")
    assert wait_for(lambda: manager.get(job["job_id"])["status"] == "completed")
    finished = manager.get(job["job_id"])
    assert finished["result"] == {"experiment_id": "abc"}
    assert finished["request"] == {"scenario": "NORMAL_DAY"}
    assert finished["started_at"] and finished["finished_at"] and finished["error"] is None


def test_job_records_the_error_when_the_work_raises():
    manager = JobManager()

    def broken():
        raise RuntimeError("PostgreSQL is not reachable")

    job = manager.submit("validation", {}, broken)
    assert wait_for(lambda: manager.get(job["job_id"])["status"] == "failed")
    failed = manager.get(job["job_id"])
    assert failed["error"] == "PostgreSQL is not reachable"
    assert failed["result"] is None


def test_jobs_run_one_at_a_time_so_measurements_do_not_overlap():
    manager = JobManager()
    release = threading.Event()
    first = manager.submit("workload", {}, lambda: release.wait(5) and {"n": 1})
    second = manager.submit("workload", {}, lambda: {"n": 2})
    assert wait_for(lambda: manager.get(first["job_id"])["status"] == "running")
    assert manager.get(second["job_id"])["status"] == "queued"
    release.set()
    assert wait_for(lambda: manager.get(second["job_id"])["status"] == "completed")
    assert [job["job_id"] for job in manager.list()] == [second["job_id"], first["job_id"]]


def test_unknown_job_is_absent():
    assert JobManager().get("missing") is None


# ---------------------------------------------------------------- latency breakdown

EVENTS = [
    {"operation": "TRANSFER", "latency_ms": 10, "success": True, "queue_wait_ms": 0},
    {"operation": "TRANSFER", "latency_ms": 30, "success": False, "queue_wait_ms": 4},
    {"operation": "BALANCE_CHECK", "latency_ms": 2, "success": True, "queue_wait_ms": None},
    {"operation": "BALANCE_CHECK", "latency_ms": 4, "success": True, "queue_wait_ms": None},
    {"operation": "BALANCE_CHECK", "latency_ms": 600, "success": True, "queue_wait_ms": None},
]


def test_latency_breakdown_summarises_each_operation_type():
    breakdown = latency_breakdown(EVENTS)
    assert breakdown["count"] == 5
    by_operation = {item["operation"]: item for item in breakdown["operations"]}
    assert by_operation["TRANSFER"] == {"operation": "TRANSFER", "count": 2, "failed": 1, "average_latency_ms": 20.0, "p50_latency_ms": 20.0, "p95_latency_ms": 29.0, "max_latency_ms": 30.0, "average_queue_wait_ms": 2.0}
    assert by_operation["BALANCE_CHECK"]["count"] == 3
    assert by_operation["BALANCE_CHECK"]["average_queue_wait_ms"] is None


def test_latency_histogram_counts_every_event_exactly_once():
    histogram = latency_breakdown(EVENTS)["histogram"]
    assert sum(bucket["count"] for bucket in histogram) == 5
    bounded = [bucket["upper_ms"] for bucket in histogram[:-1]]
    assert bounded == sorted(bounded)
    assert histogram[-1]["upper_ms"] is None  # the last bucket is open-ended
    containing_600 = next(bucket for bucket in histogram[:-1] if bucket["lower_ms"] < 600 <= bucket["upper_ms"])
    assert containing_600["count"] == 1


def test_latency_breakdown_of_no_events_is_empty():
    assert latency_breakdown([]) == {"count": 0, "operations": [], "histogram": []}


# ---------------------------------------------------------------- model registry

def test_model_registry_reads_each_stored_model(tmp_path):
    metadata = {"target": "actual_tps", "algorithm": "linear_regression", "training_samples": 5, "test_samples": 2, "feature_columns": ["scenario", "concurrency"], "metrics": {"mae": 0.35, "rmse": 0.5, "r2": 0.99}, "scenario_values": ["NORMAL_DAY"], "numeric_ranges": {"concurrency": [4.0, 12.0]}}
    (tmp_path / "actual_tps.json").write_text(json.dumps(metadata), encoding="utf-8")
    (tmp_path / "actual_tps.joblib").write_bytes(b"model")
    models = describe_models(tmp_path)
    assert len(models) == 1
    assert models[0]["target"] == "actual_tps"
    assert models[0]["metrics"]["mae"] == 0.35
    assert models[0]["numeric_ranges"] == {"concurrency": [4.0, 12.0]}
    assert models[0]["trained_at"]


def test_model_registry_is_empty_without_artifacts(tmp_path):
    assert describe_models(tmp_path / "missing") == []


# ---------------------------------------------------------------- endpoints that need no database

client = TestClient(app)


def test_scenarios_endpoint_lists_every_scenario_with_its_mix_and_the_limits():
    body = client.get("/api/scenarios").json()
    assert {item["scenario"] for item in body["scenarios"]} == {scenario.value for scenario in Scenario}
    normal = next(item for item in body["scenarios"] if item["scenario"] == "NORMAL_DAY")
    assert normal["operation_mix"] == DEFAULT_MIXES[Scenario.NORMAL_DAY]
    assert body["limits"]["max_concurrency"] == MAX_CONCURRENCY


def test_sweep_endpoint_returns_one_prediction_per_value(monkeypatch):
    monkeypatch.setattr(what_if, "predict_performance", lambda config: {"predictions": {"predicted_actual_tps": float(config["target_tps"])}, "warnings": []})
    response = client.post("/api/what-if/sweep", json={"baseline": {"scenario": "NORMAL_DAY", "concurrency": 10, "target_tps": 10}, "parameter": "target_tps", "values": [10, 20, 40]})
    assert response.status_code == 200
    body = response.json()
    assert [item["predictions"]["predicted_actual_tps"] for item in body["results"]] == [10.0, 20.0, 40.0]
    assert body["model_derived_sensitivity"]["predicted_actual_tps"] == pytest.approx(1.0)


def test_sweep_endpoint_rejects_an_unsupported_parameter():
    response = client.post("/api/what-if/sweep", json={"baseline": {"scenario": "NORMAL_DAY"}, "parameter": "duration_seconds", "values": [1, 2]})
    assert response.status_code == 422


def test_job_submission_rejects_out_of_bounds_workloads():
    response = client.post("/api/jobs", json={"kind": "workload", "workload": {"scenario": "NORMAL_DAY", "concurrency": MAX_CONCURRENCY + 1}})
    assert response.status_code == 422


def test_unknown_job_returns_404():
    assert client.get("/api/jobs/does-not-exist").status_code == 404
