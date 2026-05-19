"""Google OAuth start/callback/status/disconnect endpoints.

OAuth flow:
  1. Frontend calls `GET /api/auth/google/start?return_to=/` → returns
     authorization URL. Frontend window.location = that URL.
  2. User consents on accounts.google.com.
  3. Google redirects to `/api/auth/google/callback?code=...&state=...`.
     Backend exchanges the code for tokens, stores refresh_token + email,
     responds with HTML that closes the window or redirects back into
     the app.
  4. Frontend re-fetches `/api/auth/google/status`.
"""
from __future__ import annotations

import logging
import secrets
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.auth import RequireUser
from app.config import settings
from app.schemas import GoogleStatusOut
from app.services.gmail_oauth import (
    authorization_url,
    disconnect as oauth_disconnect,
    exchange_code,
    get_status,
    is_oauth_configured,
    store_token,
)


log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/google", tags=["oauth"])

_state_store: dict[str, str] = {}  # state -> return_to (in-memory, single-user)


def _redirect_uri(request: Request) -> str:
    """Compute the OAuth callback URL.

    Prefers PUBLIC_BASE_URL if set, otherwise reconstructs from the
    request. The path is fixed; only the origin varies between dev
    and prod.
    """
    if settings.public_base_url:
        base = settings.public_base_url.rstrip("/")
    else:
        scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
        host = request.headers.get("host") or request.url.netloc
        base = f"{scheme}://{host}"
    return f"{base}/api/auth/google/callback"


@router.get("/status", response_model=GoogleStatusOut, dependencies=[RequireUser])
def status() -> GoogleStatusOut:
    if not is_oauth_configured():
        return GoogleStatusOut(connected=False, email="", scopes=[])
    s = get_status()
    return GoogleStatusOut(
        connected=s["connected"],
        email=s["email"],
        scopes=s["scopes"],
        last_polled_at=s["last_polled_at"],
    )


@router.get("/start", dependencies=[RequireUser])
def start(request: Request, return_to: str = "/") -> JSONResponse:
    """Return an authorization URL for the frontend to redirect to."""
    if not is_oauth_configured():
        raise HTTPException(
            status_code=503,
            detail="GOOGLE_OAUTH_CLIENT_ID/SECRET not set on the server",
        )
    # Constrain return_to to a relative path to prevent open-redirect.
    parsed = urlparse(return_to)
    if parsed.scheme or parsed.netloc:
        return_to = "/"
    state = secrets.token_urlsafe(24)
    _state_store[state] = return_to
    # Bound the size to avoid leaking memory if start is hammered.
    while len(_state_store) > 32:
        _state_store.pop(next(iter(_state_store)))
    url = authorization_url(_redirect_uri(request), state)
    return JSONResponse({"authorization_url": url})


@router.get("/callback")
def callback(request: Request, code: str = "", state: str = "", error: str = "") -> HTMLResponse:
    """Handle Google's redirect after consent. No auth dep — Cloudflare Access already gated the host."""
    if error:
        return HTMLResponse(
            f"<h1>Google denied the request</h1><pre>{error}</pre>",
            status_code=400,
        )
    if not code:
        return HTMLResponse("<h1>Missing code</h1>", status_code=400)
    return_to = _state_store.pop(state, "/") if state else "/"
    try:
        refresh_token, email, scopes = exchange_code(code, _redirect_uri(request))
    except Exception as exc:
        log.exception("OAuth code exchange failed")
        return HTMLResponse(
            f"<h1>Token exchange failed</h1><pre>{exc}</pre>",
            status_code=502,
        )
    store_token(refresh_token, email, scopes)
    log.info("Gmail OAuth connected as %s (scopes=%s)", email, scopes)
    # Trigger an immediate poll in the background so items appear right away.
    try:
        from app.services.gmail_poller import poll_gmail
        import threading
        threading.Thread(target=poll_gmail, daemon=True).start()
    except Exception:
        log.exception("Failed to kick off post-connect poll")
    qs = urlencode({"connected": "1", "email": email})
    return RedirectResponse(url=f"{return_to}?{qs}", status_code=302)


@router.post("/disconnect", status_code=204, dependencies=[RequireUser])
def disconnect() -> None:
    oauth_disconnect()
