"""SQLAlchemy models."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Alert(Base):
    __tablename__ = "alert"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # Optional user-defined grouping (e.g. "Private Capital", "Personal").
    # Empty string = uncategorized.
    category: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    # Subject substring used to bucket incoming Gmail messages into this
    # alert. Default = the alert name itself (matches "Google Alert - <name>").
    subject_match: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    # Unused since 2026-05-18 (RSS ingestion removed). Kept for old rows.
    feed_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String(20), default="brand", nullable=False)
    icon: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    etag: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    last_modified: Mapped[str] = mapped_column(String(80), default="", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    items: Mapped[list["Item"]] = relationship(
        back_populates="alert", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("name", name="uq_alert_name"),
    )


class Item(Base):
    """One row per RSS entry. Dedup key is sha1(alert_id + guid)."""

    __tablename__ = "item"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    alert_id: Mapped[int] = mapped_column(
        ForeignKey("alert.id", ondelete="CASCADE"), nullable=False, index=True
    )
    guid: Mapped[str] = mapped_column(Text, default="", nullable=False)
    title: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    snippet: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_domain: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    link: Mapped[str] = mapped_column(Text, default="", nullable=False)
    original_link: Mapped[str] = mapped_column(Text, default="", nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    alert: Mapped[Alert] = relationship(back_populates="items")
    state: Mapped["ItemState | None"] = relationship(
        back_populates="item", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_item_alert_pub", "alert_id", "published_at"),
    )


class ItemState(Base):
    """Local read/saved/hidden marks. One row max per item."""

    __tablename__ = "item_state"

    item_id: Mapped[str] = mapped_column(
        ForeignKey("item.id", ondelete="CASCADE"), primary_key=True
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    saved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    item: Mapped[Item] = relationship(back_populates="state")


class Setting(Base):
    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", nullable=False)
