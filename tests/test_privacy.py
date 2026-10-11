"""On a public server a person sees the reference runs and their own, and nothing of anyone else's."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.app import access, main
from backend.app.database import engine
from backend.app.jobs import JobManager
from backend.app.main import app
from backend.app.ml.dataset import rows_to_frame
from backend.app.workload import WorkloadConfig, WorkloadRunner
from tests.test_public import SECRET, public_config, signed_in

READ_ONLY_MIX = {"BALANCE_CHECK": 1.0}
CONFIGURATION = '{"concurrency": 4, "target_tps": 10, "duration_seconds": 2}'


@pytest.fixture
def people(require_postgres, monkeypatch):
    """A reference run, a run and a validation each for two people, stamped newest so they head every list."""
    monkeypatch.setattr(access, "config", lambda: public_config())
    alice, bob = f"alice-{uuid4().hex[:8]}", f"bob-{uuid4().hex[:8]}"
    runs = {"reference": str(uuid4()), alice: str(uuid4()), bob: str(uuid4())}
    validations = {alice: str(uuid4()), bob: str(uuid4())}
    started = datetime.now(timezone.utc) + timedelta(days=3)
    with engine.begin() as connection:
        for owner, experiment_id in runs.items():
            connection.execute(text("""
                INSERT INTO experiment_runs (experiment_id, scenario, configuration, started_at, completed_at, status, actual_tps, average_latency_ms, p95_latency_ms, started_by)
                VALUES (:id, 'NORMAL_DAY', CAST(:configuration AS JSONB), :started, :completed, 'COMPLETED', 10, 8, 12, :owner)
            """), {"id": experiment_id, "configuration": CONFIGURATION, "started": started, "completed": started + timedelta(seconds=2), "owner": None if owner == "reference" else owner})
        for owner, validation_id in validations.items():
            connection.execute(text("""
                INSERT INTO validation_experiments (validation_id, prediction_id, scenario, workload_configuration, prediction_timestamp, validation_status, actual_experiment_id, started_by, created_at)
                VALUES (:id, :prediction, 'NORMAL_DAY', CAST(:configuration AS JSONB), :stamp, 'COMPLETED', :experiment, :owner, :stamp)
            """), {"id": validation_id, "prediction": str(uuid4()), "configuration": CONFIGURATION, "stamp": started, "experiment": runs[owner], "owner": owner})
    yield {"alice": alice, "bob": bob, "runs": runs, "validations": validations}
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM validation_experiments WHERE validation_id = ANY(:ids)"), {"ids": list(validations.values())})
        connection.execute(text("DELETE FROM experiment_runs WHERE experiment_id = ANY(:ids)"), {"ids": list(runs.values())})


def listed(client, path="/api/experiments?limit=10", key="experiment_id"):
    return {item[key] for item in client.get(path).json()}


# ---------------------------------------------------------------- runs

def test_a_person_sees_the_reference_runs_and_their_own_but_not_anyone_elses(people):
    runs = people["runs"]
    seen = listed(signed_in(people["alice"]))
    assert runs["reference"] in seen and runs[people["alice"]] in seen
    assert runs[people["bob"]] not in seen


def test_a_visitor_who_is_not_signed_in_sees_only_reference_runs(people):
    runs = people["runs"]
    seen = listed(TestClient(app))
    assert runs["reference"] in seen
    assert runs[people["alice"]] not in seen and runs[people["bob"]] not in seen


def test_someone_elses_run_cannot_be_opened_by_its_address(people):
    theirs = people["runs"][people["bob"]]
    for client in (signed_in(people["alice"]), TestClient(app)):
        for path in (f"/api/experiments/{theirs}", f"/api/experiments/{theirs}/latency", f"/api/recommendations/{theirs}"):
            response = client.get(path)
            assert response.status_code == 404, path  # the same answer as for a run that does not exist
    assert signed_in(people["bob"]).get(f"/api/experiments/{theirs}").status_code == 200
    assert TestClient(app).get(f"/api/experiments/{people['runs']['reference']}").status_code == 200


def test_runs_say_whether_they_are_mine_or_reference_and_never_name_an_owner(people):
    records = {run["experiment_id"]: run for run in signed_in(people["alice"]).get("/api/experiments?limit=10").json()}
    mine, reference = records[people["runs"][people["alice"]]], records[people["runs"]["reference"]]
    assert (mine["mine"], mine["reference"]) == (True, False)
    assert (reference["mine"], reference["reference"]) == (False, True)
    assert "started_by" not in mine
    detail = signed_in(people["alice"]).get(f"/api/experiments/{mine['experiment_id']}").json()["experiment"]
    assert "started_by" not in detail and detail["mine"] is True


def test_a_private_server_shows_every_run(people, monkeypatch):
    monkeypatch.setattr(access, "config", lambda: public_config(public=False))
    assert set(people["runs"].values()) <= listed(TestClient(app))


# ---------------------------------------------------------------- validations

def test_validations_follow_the_same_rule(people):
    validations = people["validations"]
    alice = signed_in(people["alice"])
    seen = listed(alice, "/api/validation?limit=10", "validation_id")
    assert validations[people["alice"]] in seen and validations[people["bob"]] not in seen
    assert alice.get(f"/api/validation/{validations[people['bob']]}").status_code == 404
    record = alice.get(f"/api/validation/{validations[people['alice']]}").json()
    assert record["validation_id"] == validations[people["alice"]] and "started_by" not in record
    assert not listed(TestClient(app), "/api/validation?limit=10", "validation_id") & set(validations.values())


def test_the_accuracy_summary_counts_everyones_checks_without_listing_them(people):
    summary = TestClient(app).get("/api/validation/summary").json()
    assert summary["validation_count"] >= 2  # both people's checks are in the totals
    assert "started_by" not in str(summary)


# ---------------------------------------------------------------- ownership is recorded when a run starts

def test_a_run_belongs_to_its_owner_from_the_moment_it_is_created(require_postgres):
    login = f"carol-{uuid4().hex[:8]}"
    seen_while_running = []
    runner = WorkloadRunner(WorkloadConfig(concurrency=2, target_tps=5, duration_seconds=1, operation_mix=READ_ONLY_MIX), started_by=login)
    original = runner._execute

    def execute(experiment_id, started_at):
        with engine.connect() as connection:
            seen_while_running.append(connection.execute(text("SELECT started_by FROM experiment_runs WHERE experiment_id = :id"), {"id": experiment_id}).scalar_one())
        return original(experiment_id, started_at)

    runner._execute = execute
    result = runner.run()
    try:
        assert seen_while_running == [login]
    finally:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM experiment_runs WHERE experiment_id = :id"), {"id": result.experiment_id})


# ---------------------------------------------------------------- jobs

def test_the_job_queue_shows_a_person_only_their_own_jobs():
    manager = JobManager()
    mine = manager.submit("workload", {"n": 1}, lambda: {"experiment_id": None}, owner="alice")
    manager.submit("workload", {"n": 2}, lambda: {"experiment_id": None}, owner="bob")
    assert [job["request"] for job in manager.list(owner="alice")] == [{"n": 1}]
    assert manager.get(mine["job_id"], owner="alice")["job_id"] == mine["job_id"]
    assert manager.get(mine["job_id"], owner="bob") is None
    assert "owner" not in manager.get(mine["job_id"], owner="alice")
    assert len(manager.list()) == 2  # no owner given: a private server sees everything


def test_a_waiting_job_reports_how_many_are_ahead_of_it():
    import threading

    manager, release = JobManager(), threading.Event()
    first = manager.submit("workload", {}, lambda: release.wait(5) and {}, owner="alice")
    second = manager.submit("workload", {}, lambda: {}, owner="bob")
    third = manager.submit("workload", {}, lambda: {}, owner="carol")
    try:
        assert manager.get(first["job_id"])["ahead"] == 0
        assert manager.get(second["job_id"])["ahead"] == 1
        assert manager.get(third["job_id"])["ahead"] == 2
    finally:
        release.set()


def test_the_jobs_endpoints_are_private_on_a_public_server(monkeypatch):
    monkeypatch.setattr(access, "config", lambda: public_config())
    monkeypatch.setattr(access, "runs_used", lambda login: 0)
    monkeypatch.setattr(access, "record_run", lambda login, kind: None)
    monkeypatch.setattr(main, "jobs", JobManager())
    monkeypatch.setattr(main, "_run_workload_job", lambda config, interval, login: {"experiment_id": None})
    alice = signed_in("alice")
    job_id = alice.post("/api/jobs", json={"kind": "workload", "workload": {"scenario": "NORMAL_DAY", "concurrency": 2, "target_tps": 5, "duration_seconds": 1}}).json()["job_id"]
    assert [job["job_id"] for job in alice.get("/api/jobs").json()] == [job_id]
    assert alice.get(f"/api/jobs/{job_id}").status_code == 200
    for other in (signed_in("bob"), TestClient(app)):
        assert other.get("/api/jobs").json() == []
        assert other.get(f"/api/jobs/{job_id}").status_code == 404


# ---------------------------------------------------------------- a slow host is not an interrupted run

def test_a_saturated_run_on_a_slow_host_is_not_mistaken_for_an_interrupted_one():
    """On a tenth of a CPU a 10-second run can take two minutes. Only a pause of many minutes means a suspended machine."""
    started = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)

    def row(elapsed):
        return {"experiment_id": str(uuid4()), "scenario": "NORMAL_DAY", "status": "COMPLETED", "configuration": {"concurrency": 8, "target_tps": 20, "duration_seconds": 10, "account_skew": 0}, "started_at": started, "completed_at": started + timedelta(seconds=elapsed)}

    assert rows_to_frame([row(11), row(127), row(1886), row(29172)])["interrupted"].tolist() == [False, False, True, True]
