from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.app.database import engine
from backend.app.main import app
from backend.app.optimization import analyze_experiment
from backend.app.telemetry import TelemetryCollector
from backend.app.workload import WorkloadConfig, WorkloadRunner

pytestmark = pytest.mark.usefixtures("require_postgres")

READ_ONLY_MIX = {"BALANCE_CHECK": 1.0}


def _delete_experiment(experiment_id):
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM experiment_runs WHERE experiment_id = :id"), {"id": experiment_id})


@pytest.fixture
def experiment_without_summary():
    experiment_id = uuid4()
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO experiment_runs (experiment_id, scenario, configuration, started_at, completed_at, status,
                                         actual_tps, average_latency_ms, p95_latency_ms, error_rate)
            VALUES (:id, 'NORMAL_DAY', CAST('{"concurrency": 4}' AS JSONB), :now, :now, 'COMPLETED', 10, 10, 30, 0)
        """), {"id": experiment_id, "now": datetime.now(timezone.utc)})
    yield str(experiment_id)
    _delete_experiment(experiment_id)


def test_experiment_detail_keeps_run_values_when_summary_is_missing(experiment_without_summary):
    record = TestClient(app).get(f"/api/experiments/{experiment_without_summary}").json()["experiment"]
    assert record["experiment_id"] == experiment_without_summary
    assert float(record["p95_latency_ms"]) == 30
    assert float(record["error_rate"]) == 0


def test_advisor_evaluates_latency_rule_when_summary_is_missing(experiment_without_summary):
    result = analyze_experiment(experiment_without_summary)
    assert "LATENCY" in {item["category"] for item in result["recommendations"]}


class RecordingCollector:
    def __init__(self):
        self.started = self.stopped = False

    def start(self, experiment_id):
        self.started = True

    def stop(self):
        self.stopped = True

    def finalize(self, result):
        raise AssertionError("a failed run must not be finalized")


def test_failed_run_is_marked_failed_and_stops_telemetry(monkeypatch):
    seen = {}

    def broken_record(self, experiment_id, result):
        seen["id"] = experiment_id
        raise RuntimeError("event store unavailable")

    monkeypatch.setattr(WorkloadRunner, "_record_event", broken_record)
    collector = RecordingCollector()
    with pytest.raises(RuntimeError, match="event store unavailable"):
        WorkloadRunner(WorkloadConfig(concurrency=1, target_tps=5, duration_seconds=0.4, operation_mix=READ_ONLY_MIX)).run(collector)
    try:
        with engine.connect() as connection:
            status = connection.execute(text("SELECT status FROM experiment_runs WHERE experiment_id = :id"), {"id": seen["id"]}).scalar_one()
        assert status == "FAILED"
        assert collector.started and collector.stopped
    finally:
        _delete_experiment(seen["id"])


def test_summary_records_the_connection_limit():
    result = WorkloadRunner(WorkloadConfig(concurrency=1, target_tps=5, duration_seconds=0.4, operation_mix=READ_ONLY_MIX)).run(TelemetryCollector(0.2))
    try:
        with engine.connect() as connection:
            limit = connection.execute(text("SELECT max_connections FROM experiment_summaries WHERE experiment_id = :id"), {"id": result.experiment_id}).scalar_one()
        assert limit and limit > 0
    finally:
        _delete_experiment(result.experiment_id)
