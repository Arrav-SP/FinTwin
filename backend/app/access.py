from __future__ import annotations

"""Who may do what when FinTwin is on the public internet.

A private server (the default) is unrestricted: it runs on its owner's machine. A public server
lets anyone read and predict, and lets a person signed in with GitHub run small workloads, a
limited number per day. Nothing here stores a password: GitHub vouches for the person, and the
browser holds a signed cookie naming their GitHub login.
"""

import base64
import hashlib
import hmac
import json
import secrets
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse

from fastapi import HTTPException, Request
from sqlalchemy import text

from .config import get_settings
from .database import engine

SESSION_COOKIE = "fintwin_session"
STATE_COOKIE = "fintwin_oauth_state"
SESSION_LIFETIME = 7 * 24 * 3600

# What a signed-in visitor may ask of a shared server. Measured 2026-10-11 under Render's free limits
# (512 MB, 0.1 CPU): the whole container delivers about 8 TPS, so these caps reach saturation but
# keep a run to well under a minute.
PUBLIC_MAX_CONCURRENCY = 8
PUBLIC_MAX_TARGET_TPS = 20.0
PUBLIC_MAX_DURATION_SECONDS = 8.0
RUNS_PER_DAY = 10
MAX_WAITING = 5  # runs execute one at a time; beyond this many waiting, new ones are turned away
PREDICTIONS_PER_MINUTE = 20
ALL_PREDICTIONS_PER_MINUTE = 120  # for all visitors together; a prediction costs real CPU on a small host


@dataclass(frozen=True)
class AccessConfig:
    public: bool
    base_url: str
    github_client_id: str
    github_client_secret: str
    session_secret: str
    dev_login: str

    @property
    def is_local(self) -> bool:
        return urlparse(self.base_url).hostname in ("localhost", "127.0.0.1", "::1")

    @property
    def github_configured(self) -> bool:
        return bool(self.github_client_id and self.github_client_secret and self.base_url)

    @property
    def dev_sign_in(self) -> bool:
        """A stand-in for GitHub while developing. Never honoured on an address other people can reach."""
        return bool(self.dev_login) and self.is_local

    @property
    def sign_in_available(self) -> bool:
        return self.github_configured or self.dev_sign_in

    @property
    def secure_cookies(self) -> bool:
        return self.base_url.startswith("https://")


# Used when no secret is configured: sessions then end when the server restarts.
_process_secret = secrets.token_urlsafe(32)


def config() -> AccessConfig:
    settings = get_settings()
    return AccessConfig(settings.public, settings.base_url.rstrip("/"), settings.github_client_id, settings.github_client_secret, settings.session_secret or _process_secret, settings.dev_login)


# ---------------------------------------------------------------- signed sessions

def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _signature(body: str, secret: str) -> str:
    return _encode(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())


def sign(payload: dict, secret: str, lifetime: int = SESSION_LIFETIME) -> str:
    """A tamper-evident token: the payload with an expiry, and an HMAC over both."""
    body = _encode(json.dumps({**payload, "exp": int(datetime.now(timezone.utc).timestamp()) + lifetime}, separators=(",", ":")).encode())
    return f"{body}.{_signature(body, secret)}"


def unsign(token: str, secret: str, now: datetime | None = None) -> dict | None:
    """The payload of a token this server signed and that has not expired; otherwise None."""
    try:
        body, signature = token.split(".")
        if not hmac.compare_digest(signature, _signature(body, secret)):
            return None
        payload = json.loads(_decode(body))
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or payload.get("exp", 0) < (now or datetime.now(timezone.utc)).timestamp():
        return None
    return payload


def viewer(request: Request) -> dict:
    """Parameters for the visibility rule: on a public server a person sees reference rows (no owner) and their own."""
    return {"public": config().public, "login": current_login(request)}


def visible(alias: str) -> str:
    """SQL for the visibility rule, to be used with the parameters from viewer()."""
    return f"(NOT :public OR {alias}.started_by IS NULL OR {alias}.started_by = :login)"


def may_see(owner: str | None, request: Request) -> bool:
    return not config().public or owner is None or owner == current_login(request)


def current_login(request: Request) -> str | None:
    payload = unsign(request.cookies.get(SESSION_COOKIE, ""), config().session_secret)
    login = payload.get("login") if payload else None
    return login if isinstance(login, str) and login else None


# ---------------------------------------------------------------- limits

class RateLimiter:
    """At most `limit` events per `window` seconds for each key, in memory."""

    def __init__(self, limit: int, window: float) -> None:
        self.limit, self.window = limit, window
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        import time

        now = time.monotonic() if now is None else now
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= now - self.window:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            if len(self._events) > 10_000:  # forget visitors who have gone quiet
                for stale in [name for name, seen in self._events.items() if not seen or seen[-1] <= now - self.window]:
                    del self._events[stale]
            return True


predictions = RateLimiter(PREDICTIONS_PER_MINUTE, 60)
# The per-visitor limit keys on an address taken from a header that a visitor can forge, so it can
# be sidestepped; this ceiling cannot.
all_predictions = RateLimiter(ALL_PREDICTIONS_PER_MINUTE, 60)


def visitor(request: Request) -> str:
    """The address a request came from. A public server sits behind its host's proxy."""
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def limit_predictions(request: Request) -> None:
    """Predictions are cheap but not free; on a public server each visitor gets a steady allowance."""
    if config().public and not (predictions.allow(visitor(request)) and all_predictions.allow("everyone")):
        raise HTTPException(status_code=429, detail="Too many predictions in a short time. Wait a minute and try again.")


def run_limits() -> dict:
    return {"max_concurrency": PUBLIC_MAX_CONCURRENCY, "max_target_tps": PUBLIC_MAX_TARGET_TPS, "max_duration_seconds": PUBLIC_MAX_DURATION_SECONDS}


def check_public_caps(concurrency: int, target_tps: float, duration_seconds: float) -> None:
    if concurrency > PUBLIC_MAX_CONCURRENCY or target_tps > PUBLIC_MAX_TARGET_TPS or duration_seconds > PUBLIC_MAX_DURATION_SECONDS:
        raise HTTPException(status_code=422, detail=f"On this shared server a run is limited to {PUBLIC_MAX_CONCURRENCY} workers, {PUBLIC_MAX_TARGET_TPS:g} TPS and {PUBLIC_MAX_DURATION_SECONDS:g} seconds.")


def runs_used(login: str) -> int:
    with engine.connect() as connection:
        return connection.execute(text("SELECT COUNT(*) FROM usage_log WHERE login = :login AND submitted_at > NOW() - INTERVAL '1 day'"), {"login": login}).scalar_one()


def record_run(login: str, kind: str) -> None:
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO usage_log (login, kind) VALUES (:login, :kind)"), {"login": login, "kind": kind})


# ---------------------------------------------------------------- GitHub

class SignInFailed(Exception):
    pass


def github_authorize_url(state: str) -> str:
    settings = config()
    # No scope is requested: only the public profile is read, to learn the login name.
    return "https://github.com/login/oauth/authorize?" + urlencode({"client_id": settings.github_client_id, "redirect_uri": f"{settings.base_url}/api/auth/callback", "state": state})


def github_login(code: str) -> str:
    """Exchange the code GitHub sent back for the login name of the person who approved."""
    import httpx

    settings = config()
    try:
        with httpx.Client(timeout=10) as client:
            token = client.post("https://github.com/login/oauth/access_token", headers={"Accept": "application/json"}, data={"client_id": settings.github_client_id, "client_secret": settings.github_client_secret, "code": code, "redirect_uri": f"{settings.base_url}/api/auth/callback"}).json().get("access_token")
            if not token:
                raise SignInFailed("GitHub did not accept the sign-in code")
            profile = client.get("https://api.github.com/user", headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}).json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SignInFailed("GitHub could not be reached") from exc
    login = profile.get("login") if isinstance(profile, dict) else None
    if not isinstance(login, str) or not login:
        raise SignInFailed("GitHub did not return a profile")
    return login
