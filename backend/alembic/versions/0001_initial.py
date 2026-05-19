"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-18

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "alert",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("feed_url", sa.Text(), nullable=False),
        sa.Column("color", sa.String(20), nullable=False, server_default="brand"),
        sa.Column("icon", sa.String(40), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_fetched_at", sa.DateTime(), nullable=True),
        sa.Column("last_status", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("etag", sa.String(200), nullable=False, server_default=""),
        sa.Column("last_modified", sa.String(80), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("name", name="uq_alert_name"),
        sa.UniqueConstraint("feed_url", name="uq_alert_feed_url"),
    )

    op.create_table(
        "item",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("alert_id", sa.Integer(),
                  sa.ForeignKey("alert.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guid", sa.Text(), nullable=False, server_default=""),
        sa.Column("title", sa.String(500), nullable=False, server_default=""),
        sa.Column("snippet", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_domain", sa.String(200), nullable=False, server_default=""),
        sa.Column("link", sa.Text(), nullable=False, server_default=""),
        sa.Column("original_link", sa.Text(), nullable=False, server_default=""),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.Column("seen_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_item_alert_id", "item", ["alert_id"])
    op.create_index("ix_item_published_at", "item", ["published_at"])
    op.create_index("ix_item_alert_pub", "item", ["alert_id", "published_at"])

    op.create_table(
        "item_state",
        sa.Column("item_id", sa.String(40),
                  sa.ForeignKey("item.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("saved_at", sa.DateTime(), nullable=True),
        sa.Column("hidden_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "setting",
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_table("setting")
    op.drop_table("item_state")
    op.drop_index("ix_item_alert_pub", table_name="item")
    op.drop_index("ix_item_published_at", table_name="item")
    op.drop_index("ix_item_alert_id", table_name="item")
    op.drop_table("item")
    op.drop_table("alert")
