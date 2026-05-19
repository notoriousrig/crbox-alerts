"""Poll Gmail for Google Alerts emails, parse, upsert items.

Pulls messages matching `from:googlealerts-noreply@google.com newer_than:Nd`,
parses each message body (plain-text or HTML), and groups results into
per-query Alert buckets. Buckets are derived from either:

  - Section headers in digest-format emails:
    `=== News - 1 new result for ["query"] ===`
  - The email Subject (`Google Alert - <query>`) for single-query emails.

Dedup state lives entirely in our DB. Item id is sha1(message_id + index).
Read-only Gmail scope — we don't mark messages read or modify them.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import re
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Alert, Item, ItemState
from app.services.gmail_oauth import (
    build_gmail_service,
    has_refresh_token,
    is_oauth_configured,
    mark_polled,
)
from app.services.url_unwrap import source_domain, unwrap


log = logging.getLogger(__name__)


_QUERY = "from:googlealerts-noreply@google.com newer_than:{days}d"
_SUBJECT_PREFIX_RE = re.compile(r"^(?:re:\s*|fwd:\s*)?google alert(?:s)?(?:\s*[-–—:])?\s*", re.I)
_WS_RE = re.compile(r"\s+")
# Section header in plain-text digest emails:
#   === News - 1 new result for ["query"] ===
# The bracketed query can wrap across soft-wrapped lines, so DOTALL.
_SECTION_RE = re.compile(
    r"===\s+(.+?)\s+-\s+\d+\s+new\s+results?\s+for\s+\[(.+?)\]\s+===",
    re.DOTALL | re.IGNORECASE,
)
# URL on its own line in plain-text emails: <https://www.google.com/url?...>
_URL_LINE_RE = re.compile(r"<(https?://[^>\s]+)>")
# Trailing truncation marker " ..."
_TRUNC_RE = re.compile(r"\s+\.{3,}\s*$")


class PollResult:
    __slots__ = ("messages_seen", "messages_new", "items_new", "duration_seconds")

    def __init__(self) -> None:
        self.messages_seen = 0
        self.messages_new = 0
        self.items_new = 0
        self.duration_seconds = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "messages_seen": self.messages_seen,
            "messages_new": self.messages_new,
            "items_new": self.items_new,
            "duration_seconds": round(self.duration_seconds, 2),
        }


def _norm_text(s: str) -> str:
    return _WS_RE.sub(" ", s or "").strip()


def _decode_body(payload: dict[str, Any]) -> str:
    """Pull the text/html part out of a Gmail message payload."""

    def walk(part: dict[str, Any]) -> str | None:
        mime = part.get("mimeType", "")
        body = part.get("body") or {}
        data = body.get("data")
        if mime == "text/html" and data:
            return base64.urlsafe_b64decode(data + "===").decode("utf-8", errors="replace")
        for sub in part.get("parts") or []:
            found = walk(sub)
            if found:
                return found
        # Fall back to text/plain if no HTML
        if mime == "text/plain" and data:
            return base64.urlsafe_b64decode(data + "===").decode("utf-8", errors="replace")
        return None

    return walk(payload) or ""


def _header(headers: list[dict[str, str]], name: str) -> str:
    name_l = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name_l:
            return h.get("value", "") or ""
    return ""


def _strip_subject_prefix(subject: str) -> str:
    """Strip 'Google Alert - ' from the subject, return the query name."""
    return _SUBJECT_PREFIX_RE.sub("", subject or "").strip()


def _extract_results_from_section(body: str) -> list[dict[str, Any]]:
    """Pull individual results from one section of a plain-text alert email.

    Each result ends with a URL line `<https://www.google.com/url?...>`.
    Text before that URL (back to the previous URL or section start) is
    the result body. We treat the first non-blank line as the title and
    everything between it and the URL as the snippet.
    """
    results: list[dict[str, Any]] = []
    cursor = 0
    for m in _URL_LINE_RE.finditer(body):
        chunk = body[cursor:m.start()]
        cursor = m.end()
        wrapped_url = m.group(1)
        # Skip Google Alerts management URLs (unsubscribe, settings, etc.)
        if "google.com/alerts" in wrapped_url or "support.google" in wrapped_url:
            continue
        link = unwrap(wrapped_url)
        if not link:
            continue
        lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
        if not lines:
            continue
        title = _TRUNC_RE.sub("", lines[0]).strip()
        if not title or len(title) < 5:
            continue
        # Drop the "... - Source" marker line if present, plus the
        # source-duplicate line that often follows.
        snippet_lines = lines[1:]
        while snippet_lines and (
            snippet_lines[0].startswith("...")
            or snippet_lines[0].startswith("- ")
        ):
            snippet_lines = snippet_lines[1:]
            if snippet_lines:
                # The next line is usually the source name on its own; skip it.
                snippet_lines = snippet_lines[1:]
            break
        snippet = _norm_text(" ".join(snippet_lines))
        results.append({
            "title": title[:500],
            "snippet": snippet,
            "link": link,
            "original_link": wrapped_url,
            "source_domain": source_domain(link),
        })
    return results


def _parse_alert_email(body: str, fallback_query: str) -> list[dict[str, Any]]:
    """Parse a Google Alerts email body (plain-text, possibly digest).

    Returns a list of items, each with a `query` key naming the alert
    bucket they belong to. Two paths:

    - **Digest format**: `=== News - N new results for ["query"] ===`
      section headers. Each section bucketed under its own query.
    - **Single-query format**: no section headers. Everything buckets
      under `fallback_query` (typically `Subject` minus `Google Alert -`).
    """
    if not body:
        return []

    sections = list(_SECTION_RE.finditer(body))
    items: list[dict[str, Any]] = []

    if sections:
        for i, m in enumerate(sections):
            query = _norm_text(m.group(2).replace("\n", " "))
            start = m.end()
            end = sections[i + 1].start() if i + 1 < len(sections) else len(body)
            for r in _extract_results_from_section(body[start:end]):
                items.append({"query": query, **r})
    else:
        for r in _extract_results_from_section(body):
            items.append({"query": fallback_query, **r})

    return items


def _find_or_create_alert(db: Session, alerts: list[Alert], query: str) -> Alert:
    """Find an existing Alert matching `query`, or auto-create one named after it."""
    needle = (query or "").strip()
    if len(needle) < 2:
        needle = "Unsorted"

    # Exact-name match first.
    for a in alerts:
        if a.name.lower() == needle.lower():
            return a
    # Then substring match against subject_match (longest wins).
    n_lower = needle.lower()
    best: Alert | None = None
    best_len = 0
    for a in alerts:
        sub = (a.subject_match or "").strip().lower()
        if sub and (sub in n_lower or n_lower in sub):
            if len(sub) > best_len:
                best = a
                best_len = len(sub)
    if best is not None:
        return best

    # Auto-create.
    name = needle[:120]
    new_alert = Alert(
        name=name,
        description="Auto-created from Google Alerts email.",
        subject_match=name,
        icon="🔔",
        sort_order=100,
    )
    db.add(new_alert)
    try:
        db.flush()
    except Exception:
        db.rollback()
        existing = db.execute(select(Alert).where(Alert.name == name)).scalar_one_or_none()
        if existing is not None:
            return existing
        raise
    log.info("Auto-created alert %r", name)
    alerts.append(new_alert)
    return new_alert


def _parse_date(headers: list[dict[str, str]]) -> datetime:
    raw = _header(headers, "Date")
    if raw:
        try:
            dt = parsedate_to_datetime(raw)
            if dt is None:
                return datetime.utcnow()
            # Normalize to naive UTC
            if dt.utcoffset() is not None:
                dt = (dt - dt.utcoffset()).replace(tzinfo=None)
            return dt
        except (TypeError, ValueError):
            pass
    return datetime.utcnow()


def _item_id(message_id: str, idx: int) -> str:
    h = hashlib.sha1(f"{message_id}:{idx}".encode("utf-8")).hexdigest()
    return h[:40]


def poll_gmail() -> PollResult:
    """Pull recent Google Alerts emails and upsert items."""
    started = time.monotonic()
    result = PollResult()

    if not is_oauth_configured() or not has_refresh_token():
        log.info("Gmail poll skipped — not connected")
        result.duration_seconds = time.monotonic() - started
        return result

    service = build_gmail_service()
    query = _QUERY.format(days=max(1, settings.gmail_lookback_days))

    msg_ids: list[str] = []
    page_token: str | None = None
    while True:
        kwargs: dict[str, Any] = {"userId": "me", "q": query, "maxResults": 100}
        if page_token:
            kwargs["pageToken"] = page_token
        resp = service.users().messages().list(**kwargs).execute()
        msg_ids.extend(m["id"] for m in resp.get("messages", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    result.messages_seen = len(msg_ids)

    if not msg_ids:
        mark_polled()
        result.duration_seconds = time.monotonic() - started
        return result

    db = SessionLocal()
    try:
        alerts = list(db.execute(select(Alert)).scalars())
        # Skip messages we've already fully processed: if any item exists
        # with guid starting with f"{msg_id}:", treat the message as seen.
        for mid in msg_ids:
            already = db.execute(
                select(Item.id).where(Item.guid.like(f"{mid}:%")).limit(1)
            ).first()
            if already is not None:
                continue
            result.messages_new += 1
            try:
                full = service.users().messages().get(
                    userId="me", id=mid, format="full",
                ).execute()
            except Exception:
                log.exception("Failed to fetch Gmail message %s", mid)
                continue

            payload = full.get("payload") or {}
            headers = payload.get("headers") or []
            subject = _header(headers, "Subject")
            published_at = _parse_date(headers)
            fallback_query = _strip_subject_prefix(subject) or "Unsorted"

            body = _decode_body(payload)
            parsed = _parse_alert_email(body, fallback_query)
            for idx, entry in enumerate(parsed):
                iid = _item_id(mid, idx)
                if db.get(Item, iid) is not None:
                    continue
                alert = _find_or_create_alert(db, alerts, entry["query"])
                db.add(Item(
                    id=iid,
                    alert_id=alert.id,
                    guid=f"{mid}:{idx}",
                    title=entry["title"],
                    snippet=entry["snippet"],
                    source_domain=entry["source_domain"],
                    link=entry["link"],
                    original_link=entry["original_link"],
                    published_at=published_at,
                ))
                alert.last_fetched_at = datetime.utcnow()
                alert.last_status = 200
                alert.last_error = ""
                result.items_new += 1

        db.commit()
    finally:
        db.close()

    mark_polled()
    result.duration_seconds = time.monotonic() - started
    log.info("Gmail poll done: %s", result.as_dict())
    return result


def prune_old_items() -> int:
    """Drop items older than ITEM_RETENTION_DAYS that have no saved_at mark."""
    if settings.item_retention_days <= 0:
        return 0
    cutoff_ts = datetime.utcnow().timestamp() - settings.item_retention_days * 86400
    cutoff_dt = datetime.fromtimestamp(cutoff_ts)
    db = SessionLocal()
    try:
        stmt = (
            select(Item.id)
            .where(Item.published_at < cutoff_dt)
            .outerjoin(ItemState, ItemState.item_id == Item.id)
            .where((ItemState.item_id.is_(None)) | (ItemState.saved_at.is_(None)))
        )
        ids = [row[0] for row in db.execute(stmt).all()]
        if not ids:
            return 0
        for iid in ids:
            obj = db.get(Item, iid)
            if obj is not None:
                db.delete(obj)
        db.commit()
        return len(ids)
    finally:
        db.close()
