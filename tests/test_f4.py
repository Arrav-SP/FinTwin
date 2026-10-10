from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.ui import mount_ui
from backend.app.validation import made_since, summarize_validations

TRAINED = datetime(2026, 10, 10, 8, 0, tzinfo=timezone.utc)


def check(predicted_tps, actual_tps, minutes_after_training, status="COMPLETED"):
    return {
        "validation_status": status, "scenario": "NORMAL_DAY", "workload_configuration": {"concurrency": 10, "target_tps": actual_tps},
        "prediction_timestamp": TRAINED + timedelta(minutes=minutes_after_training),
        "predicted_metrics": {"predicted_actual_tps": predicted_tps}, "actual_metrics": {"actual_tps": actual_tps}, "error_metrics": {},
    }


# ---------------------------------------------------------------- checks made by earlier models

def test_checks_predicted_before_the_models_were_trained_are_set_apart():
    records = [check(60, 100, -30), check(99, 100, 5), check(210, 220, 9)]
    assert made_since(records, TRAINED) == records[1:]
    assert made_since(records, None) == records


def test_timestamps_read_back_as_text_are_compared_as_times():
    record = {**check(99, 100, 5), "prediction_timestamp": (TRAINED + timedelta(minutes=5)).isoformat()}
    early = {**check(60, 100, -5), "prediction_timestamp": (TRAINED - timedelta(minutes=5)).isoformat()}
    assert made_since([early, record], TRAINED) == [record]


def test_summary_scoped_to_the_current_models_reports_how_many_checks_it_left_out():
    records = [check(60, 100, -30), check(99, 100, 5), check(210, 220, 9)]
    summary = summarize_validations(records, since=TRAINED)
    assert summary["validation_count"] == 2
    assert summary["earlier_count"] == 1
    assert summary["overall"]["actual_tps"]["mae"] == 5.5  # the 40 TPS miss of the earlier model is not counted
    assert summarize_validations(records)["validation_count"] == 3
    assert summarize_validations(records)["earlier_count"] == 0


# ---------------------------------------------------------------- serving the built UI

def client_for(root) -> TestClient:
    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"ok": True}

    mount_ui(app, root)
    return TestClient(app)


def built_ui(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>FinTwin</title><div id=root></div>", encoding="utf-8")
    (tmp_path / "assets" / "index-abc.js").write_text("console.log('ui')", encoding="utf-8")
    return tmp_path


def test_every_page_address_returns_the_app_so_a_reload_or_shared_link_works(tmp_path):
    client = client_for(built_ui(tmp_path))
    for path in ("/", "/predict", "/experiments/0b7d0f6e-1111-2222-3333-444455556666"):
        page = client.get(path)
        assert page.status_code == 200
        assert "FinTwin" in page.text


def test_built_assets_are_served_and_missing_files_are_not_answered_with_the_app(tmp_path):
    client = client_for(built_ui(tmp_path))
    assert "console.log" in client.get("/assets/index-abc.js").text
    assert client.get("/assets/missing.js").status_code == 404
    assert client.get("/app.js").status_code == 404
    assert client.get("/favicon.ico").status_code == 404


def test_the_api_keeps_its_own_answers(tmp_path):
    client = client_for(built_ui(tmp_path))
    assert client.get("/api/health").json() == {"ok": True}
    missing = client.get("/api/no-such-endpoint")
    assert missing.status_code == 404
    assert missing.headers["content-type"].startswith("application/json")


def test_an_unbuilt_ui_says_how_to_build_it(tmp_path):
    response = client_for(tmp_path).get("/")
    assert response.status_code == 503
    assert "npm --prefix web run build" in response.json()["detail"]


def test_files_outside_the_build_cannot_be_read(tmp_path):
    (tmp_path / "dist").mkdir()
    root = built_ui(tmp_path / "dist")
    (tmp_path / "secret.txt").write_text("no", encoding="utf-8")
    assert client_for(root).get("/..%2Fsecret.txt").status_code == 404
