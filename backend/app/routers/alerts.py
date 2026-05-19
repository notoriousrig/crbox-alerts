"""Alert CRUD + manual Gmail poll trigger."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import RequireUser
from app.database import get_db
from app.models import Alert, Item, ItemState
from app.schemas import AlertCreate, AlertOut, AlertUpdate, PollOut
from app.services.gmail_poller import poll_gmail


router = APIRouter(prefix="/api/alerts", tags=["alerts"], dependencies=[RequireUser])


def _alert_to_out(a: Alert, unread: int, total: int) -> AlertOut:
    return AlertOut(
        id=a.id,
        name=a.name,
        description=a.description,
        subject_match=a.subject_match or "",
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
    existing_name = db.execute(
        select(Alert).where(Alert.name == payload.name)
    ).scalar_one_or_none()
    if existing_name is not None:
        raise HTTPException(status_code=409, detail="An alert with that name already exists")

    a = Alert(
        name=payload.name,
        description=payload.description,
        subject_match=payload.subject_match or payload.name,
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


@router.post("/poll", response_model=PollOut)
def manual_poll() -> PollOut:
    """Trigger an immediate Gmail poll across all alerts."""
    try:
        result = poll_gmail()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return PollOut(
        messages_seen=result.messages_seen,
        items_new=result.items_new,
        error="",
    )
