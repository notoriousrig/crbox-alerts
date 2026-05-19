"""Google OAuth bookkeeping.

The Google Cloud project credentials (client_id / client_secret) come
from env vars. The user-specific refresh token + cached identity live
in the `setting` table — a single-user app, so one row per key.

Settings keys we use:
- google_refresh_token   — the offline refresh token (sensitive)
- google_token_email     — the gmail address that granted access
- google_token_scopes    — space-separated list of granted scopes
- google_last_polled_at  — ISO timestamp of the last successful poll
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from google.auth.transport.requests import Request as GAuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Setting


log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_URI = "https://oauth2.googleapis.com/token"
AUTH_URI = "https://accounts.google.com/o/oauth2/auth"


def _get(db: Session, key: str, default: str = "") -> str:
    row = db.get(Setting, key)
    return row.value if row else default


def _put(db: Session, key: str, value: str) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value


def _delete(db: Session, key: str) -> None:
    row = db.get(Setting, key)
    if row is not None:
        db.delete(row)


def is_oauth_configured() -> bool:
    """True if client_id/secret env vars are set."""
    return bool(settings.google_oauth_client_id and settings.google_oauth_client_secret)


def has_refresh_token() -> bool:
    db = SessionLocal()
    try:
        return bool(_get(db, "google_refresh_token"))
    finally:
        db.close()


def get_status() -> dict[str, Any]:
    db = SessionLocal()
    try:
        rt = _get(db, "google_refresh_token")
        email = _get(db, "google_token_email")
        scopes_raw = _get(db, "google_token_scopes")
        last_iso = _get(db, "google_last_polled_at")
    finally:
        db.close()
    last_dt = None
    if last_iso:
        try:
            last_dt = datetime.fromisoformat(last_iso)
        except ValueError:
            last_dt = None
    return {
        "connected": bool(rt),
        "email": email,
        "scopes": scopes_raw.split() if scopes_raw else [],
        "last_polled_at": last_dt,
    }


def store_token(refresh_token: str, email: str, scopes: list[str]) -> None:
    db = SessionLocal()
    try:
        _put(db, "google_refresh_token", refresh_token)
        _put(db, "google_token_email", email)
        _put(db, "google_token_scopes", " ".join(scopes))
        db.commit()
    finally:
        db.close()


def mark_polled(when: datetime | None = None) -> None:
    db = SessionLocal()
    try:
        _put(db, "google_last_polled_at", (when or datetime.utcnow()).isoformat())
        db.commit()
    finally:
        db.close()


def disconnect() -> None:
    db = SessionLocal()
    try:
        for k in ("google_refresh_token", "google_token_email", "google_token_scopes", "google_last_polled_at"):
            _delete(db, k)
        db.commit()
    finally:
        db.close()


def build_credentials() -> Credentials:
    """Build google-auth Credentials from the stored refresh token.

    Raises RuntimeError if not configured / not connected.
    """
    if not is_oauth_configured():
        raise RuntimeError("Google OAuth client_id/secret not configured")
    db = SessionLocal()
    try:
        rt = _get(db, "google_refresh_token")
        scopes_raw = _get(db, "google_token_scopes")
    finally:
        db.close()
    if not rt:
        raise RuntimeError("Not connected — no refresh token stored")
    creds = Credentials(
        token=None,
        refresh_token=rt,
        token_uri=TOKEN_URI,
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        scopes=scopes_raw.split() if scopes_raw else SCOPES,
    )
    creds.refresh(GAuthRequest())
    return creds


def build_gmail_service():
    """Return an authorized Gmail API client."""
    creds = build_credentials()
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def authorization_url(redirect_uri: str, state: str) -> str:
    """Build the consent URL. Caller is responsible for state generation."""
    from urllib.parse import urlencode
    params = {
        "response_type": "code",
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTH_URI}?{urlencode(params)}"


def exchange_code(code: str, redirect_uri: str) -> tuple[str, str, list[str]]:
    """Exchange an OAuth code for tokens. Returns (refresh_token, email, scopes)."""
    import httpx
    resp = httpx.post(TOKEN_URI, data={
        "code": code,
        "client_id": settings.google_oauth_client_id,
        "client_secret": settings.google_oauth_client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }, timeout=30.0)
    resp.raise_for_status()
    payload = resp.json()
    refresh_token = payload.get("refresh_token", "")
    if not refresh_token:
        raise RuntimeError(
            "Google did not return a refresh_token. Revoke the app under "
            "myaccount.google.com → Security → Third-party apps, then retry."
        )
    scope = payload.get("scope", "")
    scopes = scope.split() if scope else SCOPES

    # Identify the user by fetching their Gmail profile.
    access_token = payload.get("access_token")
    email = ""
    if access_token:
        try:
            prof = httpx.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=20.0,
            )
            prof.raise_for_status()
            email = prof.json().get("emailAddress", "") or ""
        except httpx.HTTPError:
            log.exception("Failed to fetch Gmail profile after OAuth")
    return refresh_token, email, scopes
