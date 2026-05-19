"""Item listing + per-item state mutations."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth import RequireUser
from app.database import get_db
from app.models import Alert, Item, ItemState
from app.schemas import BulkStatePatch, ItemOut, ItemStateOut, ItemStatePatch


router = APIRouter(prefix="/api/items", tags=["items"], dependencies=[RequireUser])

StateFilter = Literal["unread", "read", "saved", "hidden", "all", "inbox"]
SortMode = Literal["newest", "oldest", "source"]


def _item_to_out(it: Item, alert: Alert | None) -> ItemOut:
    return ItemOut(
        id=it.id,
        alert_id=it.alert_id,
        alert_name=alert.name if alert else "",
        alert_color=alert.color if alert else "brand",
        alert_icon=alert.icon if alert else "",
        title=it.title,
        snippet=it.snippet,
        source_domain=it.source_domain,
        link=it.link,
        published_at=it.published_at,
        seen_at=it.seen_at,
        state=ItemStateOut.model_validate(it.state) if it.state else None,
    )


@router.get("", response_model=list[ItemOut])
def list_items(
    alert_id: int | None = None,
    state: StateFilter = "inbox",
    since_hours: int | None = None,
    sort: SortMode = "newest",
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[ItemOut]:
    stmt = select(Item).options(joinedload(Item.alert), joinedload(Item.state))
    if sort == "oldest":
        stmt = stmt.order_by(Item.published_at.asc())
    elif sort == "source":
        stmt = stmt.order_by(Item.source_domain.asc(), Item.published_at.desc())
    else:  # newest
        stmt = stmt.order_by(Item.published_at.desc())
    if alert_id is not None:
        stmt = stmt.where(Item.alert_id == alert_id)
    if since_hours is not None:
        cutoff = datetime.utcnow() - timedelta(hours=since_hours)
        stmt = stmt.where(Item.published_at >= cutoff)

    stmt = stmt.outerjoin(ItemState, ItemState.item_id == Item.id)
    if state == "unread":
        stmt = stmt.where((ItemState.read_at.is_(None)) & ((ItemState.hidden_at.is_(None)) | (ItemState.item_id.is_(None))))
    elif state == "read":
        stmt = stmt.where(ItemState.read_at.is_not(None))
    elif state == "saved":
        stmt = stmt.where(ItemState.saved_at.is_not(None))
    elif state == "hidden":
        stmt = stmt.where(ItemState.hidden_at.is_not(None))
    elif state == "inbox":
        # Inbox = not hidden (default view)
        stmt = stmt.where((ItemState.hidden_at.is_(None)) | (ItemState.item_id.is_(None)))
    # "all" → no extra filter

    stmt = stmt.offset(offset).limit(limit)
    items = list(db.execute(stmt).scalars().unique())
    return [_item_to_out(it, it.alert) for it in items]


def _get_or_create_state(db: Session, item_id: str) -> ItemState:
    state = db.get(ItemState, item_id)
    if state is None:
        state = ItemState(item_id=item_id)
        db.add(state)
    return state


@router.patch("/{item_id}/state", response_model=ItemStateOut)
def patch_state(
    item_id: str, payload: ItemStatePatch, db: Session = Depends(get_db),
) -> ItemStateOut:
    it = db.get(Item, item_id)
    if it is None:
        raise HTTPException(status_code=404, detail="Item not found")
    state = _get_or_create_state(db, item_id)
    now = datetime.utcnow()
    if payload.read is not None:
        state.read_at = now if payload.read else None
    if payload.saved is not None:
        state.saved_at = now if payload.saved else None
    if payload.hidden is not None:
        state.hidden_at = now if payload.hidden else None
    db.commit()
    db.refresh(state)
    return ItemStateOut.model_validate(state)


@router.post("/bulk-state", status_code=204)
def bulk_state(payload: BulkStatePatch, db: Session = Depends(get_db)):
    if not payload.ids:
        return
    now = datetime.utcnow()
    for item_id in payload.ids:
        it = db.get(Item, item_id)
        if it is None:
            continue
        state = _get_or_create_state(db, item_id)
        if payload.action == "read":
            state.read_at = now
        elif payload.action == "unread":
            state.read_at = None
        elif payload.action == "save":
            state.saved_at = now
        elif payload.action == "unsave":
            state.saved_at = None
        elif payload.action == "hide":
            state.hidden_at = now
        elif payload.action == "unhide":
            state.hidden_at = None
    db.commit()
