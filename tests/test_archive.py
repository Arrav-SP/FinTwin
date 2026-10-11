"""The archive keeps site runs, allowances and trained models across restarts of a host that forgets its disk.

These tests use a second database in the local PostgreSQL server as the archive.
"""
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from backend.app import access, archive
from backend.app.database import engine, initialize_schema
from backend.app.main import app
from tests.test_public import public_config, signed_in

ARCHIVE_DB = "fintwin_archive_test"
CONFIGURATION = '{"concurrency": 4, "target_tps": 10, "duration_seconds": 2}'


@pytest.fixture(scope="module")
def archive_engine(require_postgres):
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        if not connection.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": ARCHIVE_DB}).first():
            connection.execute(text(f"CREATE DATABASE {ARCHIVE_DB}"))
    target = create_engine(make_url(str(engine.url.render_as_string(hide_password=False))).set(database=ARCHIVE_DB))
    initialize_schema(target_engine=target)
    yield target
    target.dispose()


@pytest.fixture
def empty_archive(archive_engine, monkeypatch):
    with archive_engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout = '10s'"))  # fail, not hang, if a connection was left open
        connection.execute(text("TRUNCATE experiment_runs, validation_experiments, usage_log, model_store CASCADE"))
    monkeypatch.setattr(archive, "engine", lambda: archive_engine)
    monkeypatch.setattr(access, "config", lambda: public_config())
    return archive_engine


@pytest.fixture
def person(require_postgres):
    login = f"dana-{uuid4().hex[:8]}"
    yield login
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM validation_experiments WHERE started_by = :login"), {"login": login})
        connection.execute(text("DELETE FROM experiment_runs WHERE started_by = :login"), {"login": login})
        connection.execute(text("DELETE FROM usage_log WHERE login = :login"), {"login": login})


def add_run(target, owner, status="COMPLETED", with_details=True):
    experiment_id = str(uuid4())
    started = datetime.now(timezone.utc) + timedelta(days=4)
    with target.begin() as connection:
        connection.execute(text("""
            INSERT INTO experiment_runs (experiment_id, scenario, configuration, started_at, completed_at, status, actual_tps, average_latency_ms, started_by)
            VALUES (:id, 'NORMAL_DAY', CAST(:configuration AS JSONB), :started, :completed, :status, 10, 8, :owner)
        """), {"id": experiment_id, "configuration": CONFIGURATION, "started": started, "completed": started + timedelta(seconds=2), "status": status, "owner": owner})
        if with_details:
            connection.execute(text("""
                INSERT INTO experiment_summaries (experiment_id, p95_latency_ms, lock_wait_count_max, host_cpu_avg_percent, latency_breakdown, generated_at)
                VALUES (:id, 12, 0, 20, CAST(:breakdown AS JSONB), NOW())
            """), {"id": experiment_id, "breakdown": json.dumps({"count": 20, "operations": [{"operation": "BALANCE_CHECK", "count": 20}], "histogram": []})})
            connection.execute(text("""
                INSERT INTO telemetry_samples (experiment_id, sample_kind, captured_at, active_connections, host_cpu_percent)
                VALUES (:id, 'SAMPLE', :at, 3, 20)
            """), {"id": experiment_id, "at": started})
            connection.execute(text("""
                INSERT INTO validation_experiments (validation_id, prediction_id, scenario, workload_configuration, prediction_timestamp, validation_status, actual_experiment_id, started_by)
                VALUES (:validation, :prediction, 'NORMAL_DAY', CAST(:configuration AS JSONB), :at, 'COMPLETED', :id, :owner)
            """), {"validation": str(uuid4()), "prediction": str(uuid4()), "configuration": CONFIGURATION, "at": started, "id": experiment_id, "owner": owner})
    return experiment_id


def count(target, sql, **params):
    with target.connect() as connection:
        return connection.execute(text(sql), params).scalar_one()


# ---------------------------------------------------------------- pushing site runs to the archive

def test_sync_archives_finished_site_runs_with_everything_that_belongs_to_them(empty_archive, person):
    finished = add_run(engine, person)
    running = add_run(engine, person, status="RUNNING", with_details=False)
    access.record_run(person, "workload")

    archive.sync()

    with empty_archive.connect() as connection:
        runs = {row[0] for row in connection.execute(text("SELECT experiment_id::text FROM experiment_runs"))}
    assert runs == {finished}  # a run still in progress is archived later, once it has finished
    assert count(empty_archive, "SELECT COUNT(*) FROM experiment_summaries WHERE experiment_id = :id", id=finished) == 1
    assert count(empty_archive, "SELECT COUNT(*) FROM telemetry_samples WHERE experiment_id = :id", id=finished) == 1
    assert count(empty_archive, "SELECT COUNT(*) FROM validation_experiments WHERE actual_experiment_id = :id", id=finished) == 1
    assert count(empty_archive, "SELECT COUNT(*) FROM usage_log WHERE login = :login", login=person) == 1
    assert running not in runs


def test_reference_runs_are_never_archived(empty_archive, require_postgres):
    reference = add_run(engine, None)
    try:
        archive.sync()
        assert count(empty_archive, "SELECT COUNT(*) FROM experiment_runs") == 0
    finally:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM validation_experiments WHERE actual_experiment_id = :id"), {"id": reference})
            connection.execute(text("DELETE FROM experiment_runs WHERE experiment_id = :id"), {"id": reference})


def test_sync_can_be_repeated_without_duplicating_anything(empty_archive, person):
    add_run(engine, person)
    access.record_run(person, "workload")
    archive.sync()
    archive.sync()
    assert count(empty_archive, "SELECT COUNT(*) FROM experiment_runs") == 1
    assert count(empty_archive, "SELECT COUNT(*) FROM telemetry_samples") == 1
    assert count(empty_archive, "SELECT COUNT(*) FROM usage_log") == 1


def test_a_failing_archive_does_not_fail_the_caller(monkeypatch):
    def unreachable():
        raise ConnectionError("archive down")

    monkeypatch.setattr(archive, "engine", lambda: create_engine("postgresql+psycopg://nobody:none@127.0.0.1:1/none", connect_args={"connect_timeout": 1}))
    assert archive.sync() is False  # logged and retried at the next sync


def test_without_an_archive_nothing_happens(monkeypatch):
    monkeypatch.setattr(archive, "engine", lambda: None)
    assert archive.sync() is False
    assert archive.restore() == 0


# ---------------------------------------------------------------- restoring after a restart

def test_restore_brings_archived_runs_back_with_their_details_and_allowances(empty_archive, person):
    archived = add_run(empty_archive, person)
    with empty_archive.begin() as connection:
        connection.execute(text("INSERT INTO usage_log (login, kind) VALUES (:login, 'workload')"), {"login": person})

    assert archive.restore() == 1
    assert count(engine, "SELECT COUNT(*) FROM experiment_runs WHERE experiment_id = :id", id=archived) == 1
    assert count(engine, "SELECT COUNT(*) FROM experiment_summaries WHERE experiment_id = :id", id=archived) == 1
    assert count(engine, "SELECT COUNT(*) FROM telemetry_samples WHERE experiment_id = :id", id=archived) == 1
    assert access.runs_used(person) == 1  # the allowance survives the restart


def test_restoring_twice_and_syncing_back_duplicates_nothing(empty_archive, person):
    """The two databases number their rows independently, so nothing may rely on those numbers matching."""
    archived = add_run(empty_archive, person)
    with empty_archive.begin() as connection:
        connection.execute(text("INSERT INTO usage_log (login, kind) VALUES (:login, 'workload')"), {"login": person})
    archive.restore()
    assert archive.restore() == 0
    access.record_run(person, "workload")
    archive.sync()
    archive.sync()
    assert count(engine, "SELECT COUNT(*) FROM telemetry_samples WHERE experiment_id = :id", id=archived) == 1
    assert count(engine, "SELECT COUNT(*) FROM usage_log WHERE login = :login", login=person) == 2
    assert count(empty_archive, "SELECT COUNT(*) FROM usage_log WHERE login = :login", login=person) == 2
    assert count(empty_archive, "SELECT COUNT(*) FROM telemetry_samples WHERE experiment_id = :id", id=archived) == 1


def test_a_restored_run_is_visible_to_its_owner_with_its_latency(empty_archive, person):
    archived = add_run(empty_archive, person)
    archive.restore()
    owner = signed_in(person)
    assert owner.get(f"/api/experiments/{archived}").status_code == 200
    latency = owner.get(f"/api/experiments/{archived}/latency").json()
    assert latency["count"] == 20  # from the breakdown stored with the run, since its events were not archived


# ---------------------------------------------------------------- trained models

def test_models_saved_to_the_archive_come_back_after_a_restart(empty_archive, tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    (models / "actual_tps.joblib").write_bytes(b"model bytes")
    (models / "actual_tps.json").write_text(json.dumps({"target": "actual_tps", "trained_at": "2026-10-11T09:00:00+00:00", "trained_on": "site"}), encoding="utf-8")
    archive.save_models(models)

    restored = tmp_path / "restored"
    archive.restore_models(restored)
    assert (restored / "actual_tps.joblib").read_bytes() == b"model bytes"
    assert json.loads((restored / "actual_tps.json").read_text(encoding="utf-8"))["trained_on"] == "site"


def test_restoring_models_does_nothing_when_none_were_trained_on_the_site(empty_archive, tmp_path):
    assert archive.restore_models(tmp_path / "models") == 0
    assert not (tmp_path / "models").exists()


# ---------------------------------------------------------------- deleting a person's data

def test_a_person_can_delete_their_runs_everywhere(empty_archive, person):
    mine = add_run(engine, person)
    access.record_run(person, "workload")
    archive.sync()

    response = signed_in(person).post("/api/auth/forget")
    assert response.status_code == 200
    assert response.json()["deleted_runs"] == 1
    for target in (engine, empty_archive):
        assert count(target, "SELECT COUNT(*) FROM experiment_runs WHERE started_by = :login", login=person) == 0
        assert count(target, "SELECT COUNT(*) FROM validation_experiments WHERE started_by = :login", login=person) == 0
        assert count(target, "SELECT COUNT(*) FROM usage_log WHERE login = :login", login=person) == 0
    assert signed_in(person).get(f"/api/experiments/{mine}").status_code == 404


def test_deleting_needs_a_sign_in(empty_archive):
    assert TestClient(app).post("/api/auth/forget").status_code == 401


# ---------------------------------------------------------------- the archive's size

def test_new_runs_are_refused_when_the_archive_is_full(empty_archive, person, monkeypatch):
    monkeypatch.setattr(archive, "MAX_ARCHIVED_RUNS", 1)
    add_run(empty_archive, person)
    monkeypatch.setattr(access, "runs_used", lambda login: 0)
    response = signed_in(person).post("/api/jobs", json={"kind": "workload", "workload": {"scenario": "NORMAL_DAY", "concurrency": 2, "target_tps": 5, "duration_seconds": 1}})
    assert response.status_code == 503
    assert "storage" in response.json()["detail"]
