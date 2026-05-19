"""Daily + weekly digest rollups, grouped by alert."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth import RequireUser
from app.database import get_db
from app.models import Alert, Item, ItemState
from app.routers.alerts import _alert_to_out, _counts_by_alert
from app.routers.items import _item_to_out
from app.schemas import DigestGroup, DigestOut


router = APIRouter(prefix="/api/digest", tags=["digest"], dependencies=[RequireUser])


def _digest(window: Literal["today", "week"], hours: int, db: Session) -> DigestOut:
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    stmt = (
        select(Item)
        .options(joinedload(Item.alert), joinedload(Item.state))
        .where(Item.published_at >= cutoff)
        .outerjoin(ItemState, ItemState.item_id == Item.id)
        .where((ItemState.hidden_at.is_(None)) | (ItemState.item_id.is_(None)))
        .order_by(Item.published_at.desc())
    )
    items = list(db.execute(stmt).scalars().unique())

    by_alert: dict[int, list[Item]] = {}
    alerts_by_id: dict[int, Alert] = {}
    for it in items:
        by_alert.setdefault(it.alert_id, []).append(it)
        if it.alert_id not in alerts_by_id and it.alert is not None:
            alerts_by_id[it.alert_id] = it.alert

    counts = _counts_by_alert(db)
    groups: list[DigestGroup] = []
    for alert_id, alert in sorted(
        alerts_by_id.items(),
        key=lambda kv: (kv[1].sort_order, kv[1].name.lower()),
    ):
        unread, total = counts.get(alert_id, (0, 0))
        groups.append(DigestGroup(
            alert=_alert_to_out(alert, unread, total),
            items=[_item_to_out(it, it.alert) for it in by_alert[alert_id]],
        ))

    return DigestOut(window=window, groups=groups, total_items=len(items))


@router.get("/today", response_model=DigestOut)
def digest_today(db: Session = Depends(get_db)) -> DigestOut:
    return _digest("today", hours=24, db=db)


@router.get("/week", response_model=DigestOut)
def digest_week(db: Session = Depends(get_db)) -> DigestOut:
    return _digest("week", hours=24 * 7, db=db)
