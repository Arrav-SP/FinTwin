"""Public mode: anyone may read and predict, signed-in people may run small workloads."""
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.app import access, main
from backend.app.config import Settings
from backend.app.database import engine
from backend.app.main import app

SECRET = "test-secret"
WORKLOAD = {"scenario": "NORMAL_DAY", "concurrency": 4, "target_tps": 10, "duration_seconds": 2}


def public_config(**overrides):
    values = dict(public=True, base_url="https://demo.example", github_client_id="client-id", github_client_secret="client-secret", session_secret=SECRET, dev_login="")
    return access.AccessConfig(**{**values, **overrides})


@pytest.fixture
def public(monkeypatch):
    """A public server with GitHub sign-in configured; nothing is really run or stored."""
    monkeypatch.setattr(access, "config", lambda: public_config())
    monkeypatch.setattr(access, "predictions", access.RateLimiter(limit=1000, window=60))
    state = {"submitted": [], "recorded": [], "used": 0, "waiting": 0}
    monkeypatch.setattr(main.jobs, "submit", lambda kind, request, work: state["submitted"].append((kind, request)) or {"job_id": "job-1", "kind": kind, "status": "queued"})
    monkeypatch.setattr(main.jobs, "waiting", lambda: state["waiting"])
    monkeypatch.setattr(access, "runs_used", lambda login: state["used"])
    monkeypatch.setattr(access, "record_run", lambda login, kind: state["recorded"].append((login, kind)))
    return state


def signed_in(login="octocat") -> TestClient:
    client = TestClient(app)
    client.cookies.set(access.SESSION_COOKIE, access.sign({"login": login}, SECRET, lifetime=3600))
    return client


# ---------------------------------------------------------------- configuration

def test_a_server_is_private_unless_the_environment_makes_it_public(monkeypatch):
    for name in ("FINTWIN_PUBLIC", "FINTWIN_BASE_URL", "GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)
    assert Settings(_env_file=None).public is False
    monkeypatch.setenv("FINTWIN_PUBLIC", "true")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "abc")
    settings = Settings(_env_file=None)
    assert settings.public is True and settings.github_client_id == "abc"


# ---------------------------------------------------------------- signed sessions

def test_a_session_survives_a_round_trip_and_nothing_else_does():
    token = access.sign({"login": "octocat"}, SECRET, lifetime=3600)
    assert access.unsign(token, SECRET)["login"] == "octocat"
    assert access.unsign(token, "another-secret") is None
    assert access.unsign(token[:-2] + ("AA" if not token.endswith("AA") else "BB"), SECRET) is None
    assert access.unsign("not-a-token", SECRET) is None
    assert access.unsign("", SECRET) is None


def test_a_session_expires():
    token = access.sign({"login": "octocat"}, SECRET, lifetime=60)
    later = datetime.now(timezone.utc) + timedelta(minutes=2)
    assert access.unsign(token, SECRET, now=later) is None


def test_a_forged_payload_with_a_valid_looking_shape_is_rejected():
    genuine = access.sign({"login": "octocat"}, SECRET, lifetime=3600)
    forged_body = access.sign({"login": "admin"}, "attacker", lifetime=3600).split(".")[0]
    assert access.unsign(f"{forged_body}.{genuine.split('.')[1]}", SECRET) is None


# ---------------------------------------------------------------- rate limiting and caps

def test_rate_limiter_allows_a_burst_then_refuses_until_the_window_passes():
    limiter = access.RateLimiter(limit=3, window=60)
    assert [limiter.allow("a", now=0), limiter.allow("a", now=1), limiter.allow("a", now=2)] == [True, True, True]
    assert limiter.allow("a", now=3) is False
    assert limiter.allow("b", now=3) is True  # another visitor is unaffected
    assert limiter.allow("a", now=61) is True


def test_public_runs_are_capped_well_below_what_the_runner_allows():
    access.check_public_caps(concurrency=16, target_tps=100, duration_seconds=10)
    for over in (dict(concurrency=17, target_tps=100, duration_seconds=10), dict(concurrency=16, target_tps=101, duration_seconds=10), dict(concurrency=16, target_tps=100, duration_seconds=11)):
        with pytest.raises(HTTPException) as refused:
            access.check_public_caps(**over)
        assert refused.value.status_code == 422
        assert "16 workers, 100 TPS and 10 seconds" in refused.value.detail


# ---------------------------------------------------------------- a private server is unchanged

def test_a_private_server_runs_jobs_for_anyone_and_reports_no_restrictions(monkeypatch):
    monkeypatch.setattr(access, "config", lambda: public_config(public=False))
    submitted = []
    monkeypatch.setattr(main.jobs, "submit", lambda kind, request, work: submitted.append(kind) or {"job_id": "job-1"})
    client = TestClient(app)
    assert client.post("/api/jobs", json={"kind": "workload", "workload": {**WORKLOAD, "concurrency": 64, "target_tps": 600}}).status_code == 202
    assert submitted == ["workload"]
    me = client.get("/api/auth/me").json()
    assert me["public"] is False and me["can_run"] is True
    assert me["run_limits"]["max_target_tps"] == 1000


# ---------------------------------------------------------------- a public server, not signed in

def test_a_visitor_can_read_and_predict_but_not_run(public):
    client = TestClient(app)
    job = client.post("/api/jobs", json={"kind": "workload", "workload": WORKLOAD})
    assert job.status_code == 401
    assert "Sign in" in job.json()["detail"]
    assert client.post("/api/validation", json=WORKLOAD).status_code == 403
    assert client.post("/api/predictions", json=WORKLOAD).status_code not in (401, 403, 429)
    assert public["submitted"] == []
    me = client.get("/api/auth/me").json()
    assert me == {**me, "public": True, "signed_in": False, "login": None, "can_run": False, "sign_in_available": True}
    assert me["run_limits"] == {"max_concurrency": 16, "max_target_tps": 100, "max_duration_seconds": 10}


def test_predictions_are_rate_limited_per_visitor_on_a_public_server(public, monkeypatch):
    monkeypatch.setattr(access, "predictions", access.RateLimiter(limit=2, window=60))
    client = TestClient(app)
    codes = [client.post("/api/predictions", json=WORKLOAD).status_code for _ in range(3)]
    assert codes[2] == 429 and 429 not in codes[:2]
    assert client.post("/api/what-if/sweep", json={"baseline": WORKLOAD, "parameter": "target_tps", "values": [10, 20]}).status_code == 429


def test_a_cookie_signed_with_another_secret_is_not_a_session(public):
    client = TestClient(app)
    client.cookies.set(access.SESSION_COOKIE, access.sign({"login": "octocat"}, "guessed", lifetime=3600))
    assert client.get("/api/auth/me").json()["signed_in"] is False
    assert client.post("/api/jobs", json={"kind": "workload", "workload": WORKLOAD}).status_code == 401


# ---------------------------------------------------------------- a public server, signed in

def test_a_signed_in_person_can_run_a_small_workload_and_it_counts_against_their_day(public):
    client = signed_in()
    response = client.post("/api/jobs", json={"kind": "validation", "workload": WORKLOAD})
    assert response.status_code == 202
    assert [kind for kind, _ in public["submitted"]] == ["validation"]
    assert public["recorded"] == [("octocat", "validation")]
    public["used"] = 3
    me = client.get("/api/auth/me").json()
    assert me == {**me, "signed_in": True, "login": "octocat", "can_run": True, "runs_per_day": 10, "runs_left": 7}


def test_a_run_above_the_public_caps_is_refused_and_does_not_use_up_the_allowance(public):
    response = signed_in().post("/api/jobs", json={"kind": "workload", "workload": {**WORKLOAD, "target_tps": 600}})
    assert response.status_code == 422
    assert public["submitted"] == [] and public["recorded"] == []


def test_the_daily_allowance_is_enforced(public):
    public["used"] = 10
    response = signed_in().post("/api/jobs", json={"kind": "workload", "workload": WORKLOAD})
    assert response.status_code == 429
    assert "10 runs" in response.json()["detail"]
    assert public["submitted"] == []


def test_a_full_queue_turns_new_runs_away_without_charging_for_them(public):
    public["waiting"] = access.MAX_WAITING
    response = signed_in().post("/api/jobs", json={"kind": "workload", "workload": WORKLOAD})
    assert response.status_code == 429
    assert public["recorded"] == []


# ---------------------------------------------------------------- signing in with GitHub

def test_sign_in_sends_the_visitor_to_github_with_a_state_only_this_browser_holds(public):
    client = TestClient(app, follow_redirects=False)
    response = client.get("/api/auth/login")
    assert response.status_code == 307
    target = urlparse(response.headers["location"])
    query = parse_qs(target.query)
    assert (target.netloc, target.path) == ("github.com", "/login/oauth/authorize")
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == ["https://demo.example/api/auth/callback"]
    assert query["state"] == [response.cookies[access.STATE_COOKIE]]
    assert "scope" not in query  # the public profile is all that is read


def test_sign_in_is_unavailable_until_github_is_configured(monkeypatch):
    monkeypatch.setattr(access, "config", lambda: public_config(github_client_id="", github_client_secret=""))
    client = TestClient(app, follow_redirects=False)
    assert client.get("/api/auth/login").status_code == 503
    assert client.get("/api/auth/me").json()["sign_in_available"] is False


def test_the_callback_refuses_a_state_it_did_not_issue(public, monkeypatch):
    monkeypatch.setattr(access, "github_login", lambda code: pytest.fail("GitHub must not be contacted"))
    client = TestClient(app, follow_redirects=False)
    client.cookies.set(access.STATE_COOKIE, "issued")
    assert client.get("/api/auth/callback?code=abc&state=forged").status_code == 400
    assert client.get("/api/auth/callback?code=abc").status_code == 400


def test_a_completed_sign_in_starts_a_session_and_sign_out_ends_it(public, monkeypatch):
    monkeypatch.setattr(access, "github_login", lambda code: "octocat" if code == "good-code" else pytest.fail("wrong code"))
    client = TestClient(app, base_url="https://demo.example", follow_redirects=False)  # a Secure cookie is only sent back over HTTPS
    client.cookies.set(access.STATE_COOKIE, "issued")
    response = client.get("/api/auth/callback?code=good-code&state=issued")
    assert response.status_code == 307 and response.headers["location"] == "/"
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
    assert client.get("/api/auth/me").json()["login"] == "octocat"
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").json()["signed_in"] is False


def test_a_failed_exchange_with_github_does_not_sign_anyone_in(public, monkeypatch):
    def refuse(code):
        raise access.SignInFailed("GitHub did not accept the code")

    monkeypatch.setattr(access, "github_login", refuse)
    client = TestClient(app, follow_redirects=False)
    client.cookies.set(access.STATE_COOKIE, "issued")
    assert client.get("/api/auth/callback?code=bad&state=issued").status_code == 502
    assert client.get("/api/auth/me").json()["signed_in"] is False


def test_the_development_sign_in_works_only_on_a_local_address(monkeypatch):
    monkeypatch.setattr(access, "config", lambda: public_config(base_url="http://127.0.0.1:8000", dev_login="tester", github_client_id="", github_client_secret=""))
    client = TestClient(app, follow_redirects=False)
    assert client.get("/api/auth/login").status_code == 307
    assert client.get("/api/auth/me").json()["login"] == "tester"

    monkeypatch.setattr(access, "config", lambda: public_config(base_url="https://demo.example", dev_login="tester", github_client_id="", github_client_secret=""))
    remote = TestClient(app, follow_redirects=False)
    assert remote.get("/api/auth/login").status_code == 503
    assert remote.get("/api/auth/me").json()["signed_in"] is False


# ---------------------------------------------------------------- who ran what (database)

@pytest.fixture
def owned_run(require_postgres):
    experiment_id, login = uuid4(), f"tester-{uuid4().hex[:8]}"
    started = datetime.now(timezone.utc) + timedelta(days=2)
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO experiment_runs (experiment_id, scenario, configuration, started_at, completed_at, status, actual_tps, average_latency_ms)
            VALUES (:id, 'NORMAL_DAY', CAST('{"concurrency": 4, "target_tps": 10, "duration_seconds": 2}' AS JSONB), :started, :completed, 'COMPLETED', 10, 8)
        """), {"id": experiment_id, "started": started, "completed": started + timedelta(seconds=2)})
    yield str(experiment_id), login
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM experiment_runs WHERE experiment_id = :id"), {"id": experiment_id})
        connection.execute(text("DELETE FROM usage_log WHERE login = :login"), {"login": login})


def test_a_run_is_marked_as_mine_only_for_the_person_who_started_it_and_names_nobody(owned_run, public):
    experiment_id, login = owned_run
    main.claim_run(experiment_id, login)

    def listed(client):
        return next(run for run in client.get("/api/experiments?limit=5").json() if run["experiment_id"] == experiment_id)

    assert listed(signed_in(login))["mine"] is True
    assert listed(signed_in("someone-else"))["mine"] is False
    anonymous = listed(TestClient(app))
    assert anonymous["mine"] is False and "started_by" not in anonymous
    assert "started_by" not in TestClient(app).get(f"/api/experiments/{experiment_id}").json()["experiment"]


def test_runs_are_counted_per_person_over_the_last_day(owned_run):
    _, login = owned_run
    assert access.runs_used(login) == 0
    access.record_run(login, "workload")
    access.record_run(login, "validation")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO usage_log (login, kind, submitted_at) VALUES (:login, 'workload', NOW() - INTERVAL '2 days')"), {"login": login})
    assert access.runs_used(login) == 2


def test_changing_the_claimed_address_does_not_lift_the_overall_ceiling_on_predictions(public, monkeypatch):
    """The visitor's address comes from a header a visitor can set, so there is a ceiling for everyone together."""
    monkeypatch.setattr(access, "predictions", access.RateLimiter(limit=1000, window=60))
    monkeypatch.setattr(access, "all_predictions", access.RateLimiter(limit=3, window=60))
    client = TestClient(app)
    codes = [client.post("/api/predictions", json=WORKLOAD, headers={"X-Forwarded-For": f"203.0.113.{n}"}).status_code for n in range(4)]
    assert codes[3] == 429 and 429 not in codes[:3]
