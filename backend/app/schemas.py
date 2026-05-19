"""Pydantic schemas for request/response."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# -------------------------- Alerts --------------------------

class AlertCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    subject_match: str = ""
    category: str = ""
    color: str = "brand"
    icon: str = ""
    sort_order: int = 0


class AlertUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    subject_match: str | None = None
    category: str | None = None
    color: str | None = None
    icon: str | None = None
    sort_order: int | None = None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    subject_match: str
    category: str
    color: str
    icon: str
    sort_order: int
    last_fetched_at: datetime | None
    last_status: int | None
    last_error: str
    created_at: datetime
    unread_count: int = 0
    total_count: int = 0


class PollOut(BaseModel):
    messages_seen: int
    items_new: int
    error: str = ""


class GoogleStatusOut(BaseModel):
    connected: bool
    email: str = ""
    scopes: list[str] = []
    last_polled_at: datetime | None = None


# -------------------------- Items --------------------------

class ItemStateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    read_at: datetime | None = None
    saved_at: datetime | None = None
    hidden_at: datetime | None = None


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_id: int
    alert_name: str = ""
    alert_color: str = "brand"
    alert_icon: str = ""
    title: str
    snippet: str
    source_domain: str
    link: str
    published_at: datetime
    seen_at: datetime
    state: ItemStateOut | None = None


class ItemStatePatch(BaseModel):
    read: bool | None = None
    saved: bool | None = None
    hidden: bool | None = None


class BulkStatePatch(BaseModel):
    ids: list[str]
    action: Literal["read", "unread", "save", "unsave", "hide", "unhide"]


# -------------------------- Digest --------------------------

class DigestGroup(BaseModel):
    alert: AlertOut
    items: list[ItemOut]


class DigestOut(BaseModel):
    window: str  # "today" or "week"
    groups: list[DigestGroup]
    total_items: int


# -------------------------- Settings --------------------------

class SettingOut(BaseModel):
    key: str
    value: str


class SettingPut(BaseModel):
    value: str
