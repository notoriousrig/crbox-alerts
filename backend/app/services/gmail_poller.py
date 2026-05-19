"""Poll Gmail for Google Alerts emails, parse, upsert items.

Pulls messages matching `from:googlealerts-noreply@google.com newer_than:Nd`,
parses the HTML body into individual alert results, buckets them by
matching the message Subject against each Alert's `subject_match` field,
and dedups on the Gmail message ID + per-message item index.

Read-only Gmail scope — we don't mark messages read or modify them.
Dedup state lives entirely in our DB (item.guid = f"{msg_id}:{index}").
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

from bs4 import BeautifulSoup
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


def _parse_alert_email(html: str) -> list[dict[str, Any]]:
    """Extract per-result items from a Google Alerts HTML email.

    Google Alerts emails wrap each result in a structure like:
      <a href="https://www.google.com/url?...&url=REAL"><b>Title</b></a>
      <div>...snippet...</div>

    We grab every <a> whose href starts with google.com/url, take the
    visible link text as the title, and the next sibling block of text
    as the snippet.
    """
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    items: list[dict[str, Any]] = []
    seen_links: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "google.com/url" not in href and "google.com/alerts" not in href:
            continue
        unwrapped = unwrap(href)
        if not unwrapped or unwrapped in seen_links:
            continue
        # Skip alert-management links (manage, edit, delete).
        if "google.com/alerts" in unwrapped:
            continue
        seen_links.add(unwrapped)

        title = _norm_text(a.get_text(" ", strip=True))
        if not title or len(title) < 5:
            continue

        # Walk forward through following siblings to find a snippet block.
        snippet = ""
        node = a
        for _ in range(6):
            node = node.find_next()
            if node is None:
                break
            if node.name == "a" and "href" in node.attrs and "google.com/url" in node["href"]:
                break  # next result starts
            text = _norm_text(node.get_text(" ", strip=True)) if hasattr(node, "get_text") else ""
            if text and text != title:
                snippet = text
                break

        items.append({
            "title": title[:500],
            "snippet": snippet,
            "link": unwrapped,
            "original_link": href,
            "source_domain": source_domain(unwrapped),
        })
    return items


def _match_alert(subject: str, alerts: list[Alert]) -> Alert | None:
    """Find the Alert whose subject_match (or name) appears in the email subject."""
    if not subject:
        return None
    subj_lower = subject.lower()
    query = _strip_subject_prefix(subject).lower()
    best: Alert | None = None
    best_len = 0
    for a in alerts:
        needle = (a.subject_match or a.name).strip().lower()
        if not needle:
            continue
        if needle in subj_lower or needle in query:
            if len(needle) > best_len:
                best = a
                best_len = len(needle)
    return best


def _auto_create_alert(db: Session, subject: str) -> Alert:
    """Derive an Alert from an email Subject line.

    Strips the "Google Alert - " prefix and uses the remainder as both
    the alert name and its subject_match. If the strip yields nothing
    usable, falls back to a single shared "Unsorted" bucket.
    """
    query = _strip_subject_prefix(subject)
    if not query or len(query) < 2:
        name = "Unsorted"
    else:
        # Truncate to fit the column (120 chars).
        name = query[:120]

    existing = db.execute(select(Alert).where(Alert.name == name)).scalar_one_or_none()
    if existing is not None:
        return existing

    a = Alert(
        name=name,
        description="Auto-created from Gmail Subject line.",
        subject_match=name,
        icon="🔔",
        sort_order=100,
    )
    db.add(a)
    try:
        db.flush()
    except Exception:
        # Race against a parallel worker that just created the same row.
        db.rollback()
        existing = db.execute(select(Alert).where(Alert.name == name)).scalar_one_or_none()
        if existing is not None:
            return existing
        raise
    log.info("Auto-created alert %r from Subject %r", name, subject)
    return a


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

            alert = _match_alert(subject, alerts)
            if alert is None:
                alert = _auto_create_alert(db, subject)
                if alert not in alerts:
                    alerts.append(alert)

            html = _decode_body(payload)
            parsed = _parse_alert_email(html)
            for idx, entry in enumerate(parsed):
                iid = _item_id(mid, idx)
                if db.get(Item, iid) is not None:
                    continue
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
                result.items_new += 1

            # Tag the alert that received items so the UI can show last-fetched.
            alert.last_fetched_at = datetime.utcnow()
            alert.last_status = 200
            alert.last_error = ""

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
