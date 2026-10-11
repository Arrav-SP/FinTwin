import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.app.bundled import install_bundled
from backend.app.database import engine
from backend.app.main import app
from backend.app.ml.registry import describe_models


# ---------------------------------------------------------------- runs interrupted by a suspended machine

@pytest.fixture
def interrupted_run(require_postgres):
    """An 8-second run that took half an hour, stamped in the future so it is the newest in the list."""
    experiment_id = uuid4()
    started = datetime.now(timezone.utc) + timedelta(days=1)
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO experiment_runs (experiment_id, scenario, configuration, started_at, completed_at, status,
                                         actual_tps, average_latency_ms, p95_latency_ms, error_rate)
            VALUES (:id, 'NORMAL_DAY', CAST('{"concurrency": 4, "target_tps": 40, "duration_seconds": 8}' AS JSONB),
                    :started, :completed, 'COMPLETED', 0.2, 61281, 541, 0)
        """), {"id": experiment_id, "started": started, "completed": started + timedelta(minutes=31)})
    yield str(experiment_id)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM experiment_runs WHERE experiment_id = :id"), {"id": experiment_id})


def test_interrupted_runs_are_left_out_of_the_list_unless_asked_for(interrupted_run):
    client = TestClient(app)
    listed = {run["experiment_id"] for run in client.get("/api/experiments?limit=5").json()}
    assert interrupted_run not in listed
    everything = {run["experiment_id"] for run in client.get("/api/experiments?limit=5&include_interrupted=true").json()}
    assert interrupted_run in everything
    assert client.get(f"/api/experiments/{interrupted_run}").status_code == 200  # still reachable by its address


# ---------------------------------------------------------------- when the models were trained

def stored_model(directory, target, **extra):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{target}.joblib").write_bytes(b"model")
    (directory / f"{target}.json").write_text(json.dumps({"target": target, "algorithm": "random_forest", **extra}), encoding="utf-8")


def test_training_time_comes_from_the_model_record_not_from_when_the_file_was_copied(tmp_path):
    stored_model(tmp_path, "actual_tps", trained_at="2026-10-10T08:03:47+00:00")
    assert describe_models(tmp_path)[0]["trained_at"] == "2026-10-10T08:03:47+00:00"


def test_models_without_a_recorded_training_time_fall_back_to_the_file_time(tmp_path):
    stored_model(tmp_path, "actual_tps")
    assert datetime.fromisoformat(describe_models(tmp_path)[0]["trained_at"]).year >= 2026


# ---------------------------------------------------------------- models and results shipped with the project

def test_bundled_files_are_installed_where_none_exist(tmp_path):
    bundled, target = tmp_path / "bundled", tmp_path / "artifacts"
    stored_model(bundled / "models", "actual_tps", trained_at="2026-10-10T08:03:47+00:00")
    (bundled / "study.json").write_text("{}", encoding="utf-8")
    (bundled / "database.sql.gz").write_bytes(b"dump")

    assert sorted(install_bundled(bundled, target)) == ["models/actual_tps.joblib", "models/actual_tps.json", "study.json"]
    assert (target / "models" / "actual_tps.joblib").read_bytes() == b"model"
    assert not (target / "database.sql.gz").exists()  # the database dump is loaded by PostgreSQL, not copied


def test_bundled_models_never_replace_models_trained_here(tmp_path):
    bundled, target = tmp_path / "bundled", tmp_path / "artifacts"
    stored_model(bundled / "models", "actual_tps")
    stored_model(bundled / "models", "p95_latency_ms")
    target.joinpath("models").mkdir(parents=True)
    (target / "models" / "actual_tps.joblib").write_bytes(b"trained here")

    assert install_bundled(bundled, target) == []  # a partly bundled, partly local model set would be inconsistent
    assert (target / "models" / "actual_tps.joblib").read_bytes() == b"trained here"
    assert not (target / "models" / "p95_latency_ms.joblib").exists()


def test_nothing_happens_without_a_bundle(tmp_path):
    assert install_bundled(tmp_path / "missing", tmp_path / "artifacts") == []
