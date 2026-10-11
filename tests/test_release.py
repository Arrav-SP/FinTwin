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


# ---------------------------------------------------------------- the folder that is pushed to the hosting service

from scripts.build_space import PART_BYTES, build_space  # noqa: E402


def test_the_space_export_is_complete_and_holds_nothing_private(tmp_path):
    project = tmp_path / "project"
    for path, content in {
        "backend/app/main.py": "app", "backend/requirements.txt": "fastapi", "backend/constraints.txt": "numpy==1",
        "backend/app/__pycache__/main.cpython-311.pyc": "x", "database/schema.sql": "sql", "scripts/serve.py": "serve",
        "web/package.json": "{}", "web/src/main.tsx": "ui", "web/node_modules/react/index.js": "x", "web/dist/index.html": "x",
        "bundled/models/actual_tps.joblib": "model", "bundled/study.json": "{}",
        "deploy/space/Dockerfile": "FROM x", "deploy/space/README.md": "---\nsdk: docker\n---", "deploy/space/start.sh": "#!/bin/bash",
        ".env": "POSTGRES_PASSWORD=secret", "tests/test_x.py": "x", "artifacts/models/a.joblib": "x",
    }.items():
        (project / path).parent.mkdir(parents=True, exist_ok=True)
        (project / path).write_text(content, encoding="utf-8")
    dump = bytes(range(256)) * 100
    (project / "bundled/database.sql.gz").write_bytes(dump)

    out = build_space(project, tmp_path / "out", part_bytes=10_000)
    files = {path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file()}

    assert {"Dockerfile", "README.md", "start.sh", "backend/app/main.py", "database/schema.sql", "scripts/serve.py", "web/src/main.tsx", "bundled/models/actual_tps.joblib"} <= files
    assert not any(name.startswith((".env", "tests/", "artifacts/", "web/node_modules/", "web/dist/", "deploy/")) or "__pycache__" in name for name in files)
    parts = sorted(out.glob("bundled/database.sql.gz.part*"))
    assert len(parts) == 3 and all(part.stat().st_size <= 10_000 for part in parts)
    assert b"".join(part.read_bytes() for part in parts) == dump  # the pieces rejoin into the original
    assert "bundled/database.sql.gz" not in files


def test_no_exported_file_is_too_large_for_a_plain_git_push():
    assert PART_BYTES < 10 * 1024 * 1024  # the hosting service refuses larger files without Git LFS


def test_rebuilding_replaces_the_previous_export(tmp_path):
    project = tmp_path / "project"
    for path in ("backend/a.py", "database/schema.sql", "scripts/serve.py", "web/package.json", "bundled/study.json", "deploy/space/Dockerfile", "deploy/space/README.md", "deploy/space/start.sh"):
        (project / path).parent.mkdir(parents=True, exist_ok=True)
        (project / path).write_text("x", encoding="utf-8")
    out = build_space(project, tmp_path / "out")
    (out / "stale.txt").write_text("left over", encoding="utf-8")
    (out / ".git").mkdir()
    (out / ".git" / "config").write_text("remote", encoding="utf-8")
    build_space(project, out)
    assert not (out / "stale.txt").exists()
    assert (out / ".git" / "config").read_text(encoding="utf-8") == "remote"  # the link to the hosting repository is kept


def test_shell_scripts_are_exported_with_unix_line_endings(tmp_path):
    """A checkout on Windows may hold CRLF endings, which make a script fail inside a Linux container."""
    project = tmp_path / "project"
    for path in ("backend/a.py", "database/schema.sql", "scripts/serve.py", "web/package.json", "bundled/study.json", "deploy/space/Dockerfile", "deploy/space/README.md"):
        (project / path).parent.mkdir(parents=True, exist_ok=True)
        (project / path).write_text("x", encoding="utf-8")
    (project / "deploy/space/start.sh").write_bytes(b"#!/bin/bash\r\nset -e\r\nexec python scripts/serve.py\r\n")
    out = build_space(project, tmp_path / "out")
    assert (out / "start.sh").read_bytes() == b"#!/bin/bash\nset -e\nexec python scripts/serve.py\n"
