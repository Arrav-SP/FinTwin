from __future__ import annotations

import hmac
import secrets
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from . import access
from .limits import MAX_CONCURRENCY, MAX_DURATION_SECONDS, MAX_TARGET_TPS

router = APIRouter(prefix="/api/auth")


def _start_session(response: Response, login: str) -> None:
    settings = access.config()
    response.set_cookie(access.SESSION_COOKIE, access.sign({"login": login}, settings.session_secret), max_age=access.SESSION_LIFETIME, httponly=True, secure=settings.secure_cookies, samesite="lax", path="/")


@router.get("/me")
def me(request: Request) -> dict[str, Any]:
    """What this browser may do, so the interface can show the right controls."""
    settings = access.config()
    if not settings.public:
        return {"public": False, "sign_in_available": False, "signed_in": False, "login": None, "can_run": True, "run_limits": {"max_concurrency": MAX_CONCURRENCY, "max_target_tps": MAX_TARGET_TPS, "max_duration_seconds": MAX_DURATION_SECONDS}, "runs_per_day": None, "runs_left": None}
    login = access.current_login(request)
    return {
        "public": True,
        "sign_in_available": settings.sign_in_available,
        "signed_in": login is not None,
        "login": login,
        "can_run": login is not None,
        "run_limits": access.run_limits(),
        "runs_per_day": access.RUNS_PER_DAY,
        "runs_left": max(access.RUNS_PER_DAY - access.runs_used(login), 0) if login else None,
    }


@router.get("/login")
def login() -> Response:
    settings = access.config()
    if settings.dev_sign_in:
        response = RedirectResponse("/")
        _start_session(response, settings.dev_login)
        return response
    if not settings.github_configured:
        raise HTTPException(status_code=503, detail="Sign-in is not configured on this server.")
    state = secrets.token_urlsafe(24)
    response = RedirectResponse(access.github_authorize_url(state))
    # The state comes back from GitHub in the address; only the browser that started holds the cookie.
    response.set_cookie(access.STATE_COOKIE, state, max_age=600, httponly=True, secure=settings.secure_cookies, samesite="lax", path="/api/auth")
    return response


@router.get("/callback")
def callback(request: Request, code: str = "", state: str = "") -> Response:
    settings = access.config()
    if not settings.github_configured:
        raise HTTPException(status_code=503, detail="Sign-in is not configured on this server.")
    issued = request.cookies.get(access.STATE_COOKIE, "")
    if not code or not state or not issued or not hmac.compare_digest(state, issued):
        raise HTTPException(status_code=400, detail="This sign-in link is not valid any more. Start again from the site.")
    try:
        login = access.github_login(code)
    except access.SignInFailed as exc:
        raise HTTPException(status_code=502, detail=f"Sign-in did not complete: {exc}.") from exc
    response = RedirectResponse("/")
    _start_session(response, login)
    response.delete_cookie(access.STATE_COOKIE, path="/api/auth")
    return response


@router.post("/logout")
def logout() -> Response:
    response = Response(status_code=204)
    response.delete_cookie(access.SESSION_COOKIE, path="/")
    return response
