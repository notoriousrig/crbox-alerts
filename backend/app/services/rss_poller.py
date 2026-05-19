"""Poll Google Alerts RSS/Atom feeds, upsert items.

Each Alert row has a `feed_url` that the user pasted from Google Alerts
("Deliver to: RSS feed"). We hit it with conditional GET (ETag /
If-Modified-Since), parse with feedparser, unwrap Google's redirect
wrapper, and upsert by (alert_id, guid).
"""
from __future__ import annotations

import hashlib
import html
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

import feedparser
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Alert, Item, ItemState
from app.services.url_unwrap import source_domain, unwrap


log = logging.getLogger(__name__)


_USER_AGENT = "crbox-alerts/0.1 (+https://alerts.crbox.ca)"
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


class PollResult:
    __slots__ = (
        "alerts_polled", "alerts_failed",
        "items_new", "items_updated", "duration_seconds",
    )

    def __init__(self) -> None:
        self.alerts_polled = 0
        self.alerts_failed = 0
        self.items_new = 0
        self.items_updated = 0
        self.duration_seconds = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "alerts_polled": self.alerts_polled,
            "alerts_failed": self.alerts_failed,
            "items_new": self.items_new,
            "items_updated": self.items_updated,
            "duration_seconds": round(self.duration_seconds, 2),
        }


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def _item_id(alert_id: int, guid: str) -> str:
    h = hashlib.sha1(f"{alert_id}:{guid}".encode("utf-8")).hexdigest()
    return h[:40]


def _fetch_one(
    client: httpx.Client, feed_url: str, etag: str, last_modified: str,
) -> tuple[int, bytes | None, str, str, str]:
    """Return (status, body_or_none, new_etag, new_last_modified, error)."""
    headers: dict[str, str] = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    try:
        resp = client.get(feed_url, headers=headers)
    except httpx.HTTPError as exc:
        return 0, None, etag, last_modified, str(exc)[:500]

    new_etag = resp.headers.get("ETag", etag)
    new_lm = resp.headers.get("Last-Modified", last_modified)

    if resp.status_code == 304:
        return 304, None, new_etag, new_lm, ""
    if resp.status_code >= 400:
        return resp.status_code, None, new_etag, new_lm, f"HTTP {resp.status_code}"
    return resp.status_code, resp.content, new_etag, new_lm, ""


def _parse_published(entry: Any) -> datetime | None:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not parsed:
        return None
    return datetime.fromtimestamp(time.mktime(parsed), tz=timezone.utc).replace(tzinfo=None)


def _extract_item(entry: Any) -> dict[str, Any] | None:
    guid = getattr(entry, "id", "") or getattr(entry, "link", "") or ""
    if not guid:
        return None
    published_at = _parse_published(entry)
    if not published_at:
        return None

    title = _strip_html(getattr(entry, "title", "") or "")

    snippet = ""
    content = getattr(entry, "content", None)
    if isinstance(content, list) and content:
        snippet = _strip_html(content[0].get("value", "") or "")
    if not snippet:
        snippet = _strip_html(getattr(entry, "summary", "") or "")

    original_link = getattr(entry, "link", "") or ""
    link = unwrap(original_link)

    return {
        "guid": guid,
        "title": title[:500],
        "snippet": snippet,
        "original_link": original_link,
        "link": link,
        "source_domain": source_domain(link),
        "published_at": published_at,
    }


def _upsert_items(db: Session, alert_id: int, parsed_feed: Any) -> tuple[int, int]:
    new_count = 0
    updated_count = 0

    for entry in parsed_feed.entries or []:
        v = _extract_item(entry)
        if not v:
            continue
        item_id = _item_id(alert_id, v["guid"])
        existing = db.get(Item, item_id)
        if existing is None:
            db.add(Item(
                id=item_id,
                alert_id=alert_id,
                guid=v["guid"],
                title=v["title"],
                snippet=v["snippet"],
                source_domain=v["source_domain"],
                link=v["link"],
                original_link=v["original_link"],
                published_at=v["published_at"],
            ))
            new_count += 1
        else:
            changed = False
            if existing.title != v["title"]:
                existing.title = v["title"]
                changed = True
            if existing.snippet != v["snippet"]:
                existing.snippet = v["snippet"]
                changed = True
            # Sometimes Google updates a link mid-flight (paywall → archive etc.)
            if existing.link != v["link"]:
                existing.link = v["link"]
                existing.source_domain = v["source_domain"]
                changed = True
            if changed:
                updated_count += 1
    return new_count, updated_count


def poll_alert(alert_id: int) -> dict[str, Any]:
    """Poll a single alert. Returns counts."""
    db = SessionLocal()
    try:
        a = db.get(Alert, alert_id)
        if a is None:
            return {"error": "Alert not found"}
        with httpx.Client(
            timeout=20.0,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/atom+xml,application/rss+xml,*/*"},
            follow_redirects=True,
        ) as client:
            status, body, new_etag, new_lm, err = _fetch_one(
                client, a.feed_url, a.etag, a.last_modified,
            )
        a.last_fetched_at = datetime.utcnow()
        a.last_status = status
        a.last_error = err
        a.etag = new_etag or ""
        a.last_modified = new_lm or ""

        if status == 304 or body is None:
            db.commit()
            return {"status": status, "new": 0, "updated": 0, "error": err}

        parsed = feedparser.parse(body)
        new_count, upd_count = _upsert_items(db, alert_id, parsed)
        db.commit()
        return {"status": status, "new": new_count, "updated": upd_count, "error": ""}
    finally:
        db.close()


def poll_all(alert_ids: list[int] | None = None) -> PollResult:
    started = time.monotonic()
    result = PollResult()

    db = SessionLocal()
    try:
        if alert_ids is None:
            ids = [a.id for a in db.execute(select(Alert)).scalars()]
        else:
            ids = list(alert_ids)
    finally:
        db.close()

    if not ids:
        result.duration_seconds = time.monotonic() - started
        return result

    workers = max(1, min(settings.poll_concurrency, len(ids)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(poll_alert, aid): aid for aid in ids}
        for f in as_completed(futures):
            aid = futures[f]
            try:
                outcome = f.result()
            except Exception:
                log.exception("Poll crashed for alert %s", aid)
                result.alerts_failed += 1
                continue
            if outcome.get("error") and not outcome.get("status"):
                result.alerts_failed += 1
                continue
            status = outcome.get("status", 0)
            if status == 0 or status >= 400:
                result.alerts_failed += 1
                continue
            result.alerts_polled += 1
            result.items_new += outcome.get("new", 0)
            result.items_updated += outcome.get("updated", 0)

    result.duration_seconds = time.monotonic() - started
    log.info(
        "Poll done — %d ok, %d failed, %d new, %d updated, %.1fs",
        result.alerts_polled, result.alerts_failed,
        result.items_new, result.items_updated, result.duration_seconds,
    )
    return result


def validate_feed(feed_url: str) -> tuple[bool, str]:
    """Hit the feed once to confirm it parses. Returns (ok, error_message)."""
    try:
        with httpx.Client(
            timeout=15.0,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/atom+xml,application/rss+xml,*/*"},
            follow_redirects=True,
        ) as client:
            resp = client.get(feed_url)
    except httpx.HTTPError as exc:
        return False, f"Fetch failed: {exc}"
    if resp.status_code >= 400:
        return False, f"HTTP {resp.status_code}"
    parsed = feedparser.parse(resp.content)
    if parsed.bozo and not parsed.entries:
        reason = getattr(parsed, "bozo_exception", "unknown parse error")
        return False, f"Not a valid feed: {reason}"
    return True, ""


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
