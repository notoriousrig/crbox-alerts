"""Alert CRUD + manual poll trigger."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import RequireUser
from app.database import get_db
from app.models import Alert, Item, ItemState
from app.schemas import AlertCreate, AlertOut, AlertUpdate, PollOut
from app.services.rss_poller import poll_alert, validate_feed


router = APIRouter(prefix="/api/alerts", tags=["alerts"], dependencies=[RequireUser])


def _alert_to_out(a: Alert, unread: int, total: int) -> AlertOut:
    return AlertOut(
        id=a.id,
        name=a.name,
        description=a.description,
        feed_url=a.feed_url,
        color=a.color,
        icon=a.icon,
        sort_order=a.sort_order,
        last_fetched_at=a.last_fetched_at,
        last_status=a.last_status,
        last_error=a.last_error,
        created_at=a.created_at,
        unread_count=unread,
        total_count=total,
    )


def _counts_by_alert(db: Session) -> dict[int, tuple[int, int]]:
    """Return {alert_id: (unread_count, total_count)} in two queries."""
    totals_stmt = select(Item.alert_id, func.count(Item.id)).group_by(Item.alert_id)
    totals = {aid: tot for aid, tot in db.execute(totals_stmt).all()}

    unread_stmt = (
        select(Item.alert_id, func.count(Item.id))
        .outerjoin(ItemState, ItemState.item_id == Item.id)
        .where((ItemState.read_at.is_(None)) & ((ItemState.hidden_at.is_(None)) | (ItemState.item_id.is_(None))))
        .group_by(Item.alert_id)
    )
    unread = {aid: u for aid, u in db.execute(unread_stmt).all()}
    out: dict[int, tuple[int, int]] = {}
    for aid in set(totals) | set(unread):
        out[aid] = (unread.get(aid, 0), totals.get(aid, 0))
    return out


@router.get("", response_model=list[AlertOut])
def list_alerts(db: Session = Depends(get_db)) -> list[AlertOut]:
    alerts = list(db.execute(
        select(Alert).order_by(Alert.sort_order, Alert.name)
    ).scalars())
    counts = _counts_by_alert(db)
    return [_alert_to_out(a, *counts.get(a.id, (0, 0))) for a in alerts]


@router.post("", response_model=AlertOut, status_code=201)
def create_alert(payload: AlertCreate, db: Session = Depends(get_db)) -> AlertOut:
    ok, err = validate_feed(payload.feed_url)
    if not ok:
        raise HTTPException(status_code=400, detail=err)

    existing_name = db.execute(
        select(Alert).where(Alert.name == payload.name)
    ).scalar_one_or_none()
    if existing_name is not None:
        raise HTTPException(status_code=409, detail="An alert with that name already exists")

    existing_url = db.execute(
        select(Alert).where(Alert.feed_url == payload.feed_url)
    ).scalar_one_or_none()
    if existing_url is not None:
        raise HTTPException(status_code=409, detail="That feed URL is already tracked")

    a = Alert(
        name=payload.name,
        description=payload.description,
        feed_url=payload.feed_url,
        color=payload.color,
        icon=payload.icon,
        sort_order=payload.sort_order,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return _alert_to_out(a, 0, 0)


@router.patch("/{alert_id}", response_model=AlertOut)
def update_alert(
    alert_id: int, payload: AlertUpdate, db: Session = Depends(get_db),
) -> AlertOut:
    a = db.get(Alert, alert_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    data = payload.model_dump(exclude_unset=True)
    if "feed_url" in data and data["feed_url"] != a.feed_url:
        ok, err = validate_feed(data["feed_url"])
        if not ok:
            raise HTTPException(status_code=400, detail=err)
        # Reset poll bookkeeping so we re-fetch fresh.
        a.etag = ""
        a.last_modified = ""
    for k, v in data.items():
        setattr(a, k, v)
    db.commit()
    db.refresh(a)
    counts = _counts_by_alert(db).get(a.id, (0, 0))
    return _alert_to_out(a, *counts)


@router.delete("/{alert_id}", status_code=204)
def delete_alert(alert_id: int, db: Session = Depends(get_db)) -> None:
    a = db.get(Alert, alert_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.delete(a)
    db.commit()


@router.post("/{alert_id}/poll", response_model=PollOut)
def manual_poll(alert_id: int, db: Session = Depends(get_db)) -> PollOut:
    a = db.get(Alert, alert_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    result = poll_alert(alert_id)
    if "error" in result and "status" not in result:
        raise HTTPException(status_code=502, detail=result["error"])
    return PollOut(
        status=result.get("status", 0),
        new=result.get("new", 0),
        updated=result.get("updated", 0),
        error=result.get("error", "") or "",
    )
