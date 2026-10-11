"""On a public server the models are retrained on the runs made there, once there are enough."""
import json

import pytest

pytest.importorskip("sklearn")

from fastapi.testclient import TestClient

from backend.app import access, archive, main
from backend.app.jobs import JobManager
from backend.app.main import app
from backend.app.ml import predict, retrain, train
from backend.app.ml.dataset import rows_to_frame
from tests.test_m3_ml import run_row, synthetic_rows
from tests.test_public import public_config


def site_and_reference_frame():
    """24 runs made on the site by two people, and 24 reference runs that are three times slower."""
    site = [{**row, "started_by": "alice" if index % 2 else "bob"} for index, row in enumerate(synthetic_rows())]
    reference = [{**row, "experiment_id": row["experiment_id"] + "-ref", "average_latency_ms": row["average_latency_ms"] * 3, "started_by": None} for row in synthetic_rows()]
    return rows_to_frame(site + reference)


# ---------------------------------------------------------------- what the models are trained on

def test_site_training_uses_everyones_site_runs_and_no_reference_runs():
    frame = site_and_reference_frame()
    assert len(train.training_rows(frame)) == 48
    site = train.training_rows(frame, site_only=True)
    assert len(site) == 24
    assert set(site["started_by"]) == {"alice", "bob"}


def test_models_record_whether_they_were_trained_on_the_site(monkeypatch, tmp_path):
    frame = site_and_reference_frame()
    monkeypatch.setattr(train, "load_experiments", lambda: (frame, 0))
    on_site = train.train_models(tmp_path / "site", site_only=True)["average_latency_ms"]
    everything = train.train_models(tmp_path / "all")["average_latency_ms"]
    assert (on_site["trained_on"], on_site["training_samples"]) == ("site", 24)
    assert (everything["trained_on"], everything["training_samples"]) == ("reference", 48)
    assert "started_by" not in json.dumps(on_site)  # a model card names nobody


# ---------------------------------------------------------------- when to retrain

def test_retraining_waits_for_enough_site_runs_and_then_for_enough_new_ones():
    assert retrain.due(site_runs=59, trained_at_runs=None, minimum=60, every=25) is False
    assert retrain.due(site_runs=60, trained_at_runs=None, minimum=60, every=25) is True
    assert retrain.due(site_runs=70, trained_at_runs=60, minimum=60, every=25) is False
    assert retrain.due(site_runs=85, trained_at_runs=60, minimum=60, every=25) is True


def write_model(directory, target, payload, **metadata):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{target}.joblib").write_bytes(payload)
    (directory / f"{target}.json").write_text(json.dumps({"target": target, **metadata}), encoding="utf-8")


def test_the_run_count_at_the_last_site_training_is_read_from_the_models(tmp_path):
    assert retrain.trained_at_runs(tmp_path) is None
    write_model(tmp_path, "actual_tps", b"x", trained_on="reference", training_samples=247)
    assert retrain.trained_at_runs(tmp_path) is None  # laptop models do not count as a site training
    write_model(tmp_path, "actual_tps", b"x", trained_on="site", site_runs_at_training=85)
    assert retrain.trained_at_runs(tmp_path) == 85


def test_a_successful_retraining_replaces_the_models_and_saves_them_to_the_archive(monkeypatch, tmp_path):
    frame = site_and_reference_frame()
    monkeypatch.setattr(train, "load_experiments", lambda: (frame, 0))
    saved = []
    monkeypatch.setattr(archive, "save_models", lambda directory: saved.append(directory) or True)
    models = tmp_path / "models"
    write_model(models, "average_latency_ms", b"laptop model", trained_on="reference")

    result = retrain.retrain(models, site_runs=24)

    card = json.loads((models / "average_latency_ms.json").read_text(encoding="utf-8"))
    assert (card["trained_on"], card["site_runs_at_training"]) == ("site", 24)
    assert (models / "average_latency_ms.joblib").read_bytes() != b"laptop model"
    assert saved == [models]
    assert result["trained_on"] == "site" and result["training_samples"] == 24
    assert not (tmp_path / "models.new").exists()  # nothing half-written is left behind


def test_a_failed_retraining_leaves_the_current_models_untouched(monkeypatch, tmp_path):
    frame = rows_to_frame([{**row, "started_by": "alice"} for row in synthetic_rows()[:3]])  # far too few runs
    monkeypatch.setattr(train, "load_experiments", lambda: (frame, 0))
    monkeypatch.setattr(archive, "save_models", lambda directory: pytest.fail("nothing to save"))
    models = tmp_path / "models"
    write_model(models, "average_latency_ms", b"laptop model", trained_on="reference")
    with pytest.raises(ValueError, match="Insufficient"):
        retrain.retrain(models, site_runs=3)
    assert (models / "average_latency_ms.joblib").read_bytes() == b"laptop model"
    assert json.loads((models / "average_latency_ms.json").read_text(encoding="utf-8"))["trained_on"] == "reference"


# ---------------------------------------------------------------- the trigger

@pytest.fixture
def trigger(monkeypatch):
    monkeypatch.setattr(access, "config", lambda: public_config())
    monkeypatch.setattr(archive, "sync", lambda: True)
    queued = []
    manager = JobManager()
    monkeypatch.setattr(manager, "submit", lambda kind, request, work, owner=None: queued.append((kind, owner)) or {"job_id": "t"})
    monkeypatch.setattr(main, "jobs", manager)
    monkeypatch.setattr(retrain, "site_runs", lambda: 60)
    monkeypatch.setattr(retrain, "trained_at_runs", lambda directory=None: None)
    main._training_attempted_at.clear()
    return {"queued": queued, "manager": manager}


def test_enough_site_runs_queue_one_training_job_that_belongs_to_nobody(trigger):
    main._after_run(None)
    main._after_run(None)  # the attempt is remembered, so a second run does not queue a second training
    assert trigger["queued"] == [("training", None)]


def test_no_training_is_queued_on_a_private_server(trigger, monkeypatch):
    monkeypatch.setattr(access, "config", lambda: public_config(public=False))
    main._after_run(None)
    assert trigger["queued"] == []


def test_no_training_is_queued_before_there_are_enough_runs(trigger, monkeypatch):
    monkeypatch.setattr(retrain, "site_runs", lambda: 59)
    main._after_run(None)
    assert trigger["queued"] == []


def test_a_public_server_reports_how_far_the_site_data_has_come(trigger, monkeypatch):
    monkeypatch.setattr(retrain, "site_runs", lambda: 12)
    status = TestClient(app).get("/api/system/status").json()
    assert (status["site_runs"], status["site_runs_needed"]) == (12, 60)
    monkeypatch.setattr(access, "config", lambda: public_config(public=False))
    assert TestClient(app).get("/api/system/status").json()["site_runs"] is None


# ---------------------------------------------------------------- loaded models are kept in memory

def test_a_model_is_read_from_disk_once_and_again_only_when_it_changes(monkeypatch, tmp_path):
    frame = site_and_reference_frame()
    monkeypatch.setattr(train, "load_experiments", lambda: (frame, 0))
    train.train_models(tmp_path)
    predict.forget_loaded_models()
    loads = []
    real_load = predict.joblib.load
    monkeypatch.setattr(predict.joblib, "load", lambda path: loads.append(path) or real_load(path))
    workload = {"scenario": "NORMAL_DAY", "concurrency": 8, "target_tps": 60.0, "duration_seconds": 8}

    first = predict.predict_performance(workload, tmp_path)
    second = predict.predict_performance(workload, tmp_path)
    assert first == second
    assert len(loads) == 5  # one per target, not one per prediction

    train.train_models(tmp_path, site_only=True)  # new files on disk
    predict.predict_performance(workload, tmp_path)
    assert len(loads) == 10
