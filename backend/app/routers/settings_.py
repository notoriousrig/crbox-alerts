"""Key-value settings store."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import RequireUser
from app.database import get_db
from app.models import Setting
from app.schemas import SettingOut, SettingPut


router = APIRouter(prefix="/api/settings", tags=["settings"], dependencies=[RequireUser])


@router.get("/{key}", response_model=SettingOut)
def get_setting(key: str, db: Session = Depends(get_db)) -> SettingOut:
    s = db.get(Setting, key)
    if s is None:
        raise HTTPException(status_code=404, detail="Setting not found")
    return SettingOut(key=s.key, value=s.value)


@router.put("/{key}", response_model=SettingOut)
def put_setting(key: str, payload: SettingPut, db: Session = Depends(get_db)) -> SettingOut:
    s = db.get(Setting, key)
    if s is None:
        s = Setting(key=key, value=payload.value)
        db.add(s)
    else:
        s.value = payload.value
    db.commit()
    return SettingOut(key=key, value=payload.value)
