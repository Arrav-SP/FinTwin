import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.app.database import engine
from backend.app.main import app
from backend.app.workload import WorkloadConfig, WorkloadRunner

pytestmark = pytest.mark.usefixtures("require_postgres")

READ_ONLY_MIX = {"BALANCE_CHECK": 1.0}
client = TestClient(app)


def _delete_experiment(experiment_id):
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM experiment_runs WHERE experiment_id = :id"), {"id": experiment_id})


@pytest.fixture
def small_run():
    result = WorkloadRunner(WorkloadConfig(concurrency=2, target_tps=10, duration_seconds=0.5, operation_mix=READ_ONLY_MIX)).run()
    yield result
    _delete_experiment(result.experiment_id)


def test_every_operation_records_how_long_it_waited_for_a_worker(small_run):
    with engine.connect() as connection:
        waits = connection.execute(text("SELECT queue_wait_ms FROM workload_events WHERE experiment_id = :id"), {"id": small_run.experiment_id}).scalars().all()
    assert len(waits) == small_run.completed_operations
    assert all(wait is not None and wait >= 0 for wait in waits)


def test_latency_endpoint_breaks_a_run_down_by_operation(small_run):
    body = client.get(f"/api/experiments/{small_run.experiment_id}/latency").json()
    assert body["count"] == small_run.completed_operations
    assert [item["operation"] for item in body["operations"]] == ["BALANCE_CHECK"]
    assert body["operations"][0]["average_queue_wait_ms"] is not None


def test_latency_endpoint_returns_404_for_an_unknown_run():
    assert client.get("/api/experiments/00000000-0000-0000-0000-000000000000/latency").status_code == 404


def test_workload_job_runs_in_the_background_and_reports_its_experiment():
    submitted = client.post("/api/jobs", json={"kind": "workload", "workload": {"scenario": "NORMAL_DAY", "concurrency": 2, "target_tps": 10, "duration_seconds": 0.5, "operation_mix": READ_ONLY_MIX}, "telemetry_interval": 0.2})
    assert submitted.status_code == 202
    job_id = submitted.json()["job_id"]
    deadline = time.monotonic() + 20
    job = submitted.json()
    while job["status"] in ("queued", "running") and time.monotonic() < deadline:
        time.sleep(0.1)
        job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "completed", job
    experiment_id = job["result"]["experiment_id"]
    try:
        assert client.get(f"/api/experiments/{experiment_id}").json()["experiment"]["status"] == "COMPLETED"
    finally:
        _delete_experiment(experiment_id)
