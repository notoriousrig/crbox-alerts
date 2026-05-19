"""switch ingestion: feed_url nullable, add subject_match

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-18

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite-friendly column ops via batch mode.
    with op.batch_alter_table("alert") as batch:
        # feed_url is no longer used (RSS ingestion is gone), but we keep
        # the column so old rows survive. Make it nullable + drop unique.
        batch.drop_constraint("uq_alert_feed_url", type_="unique")
        batch.alter_column("feed_url", existing_type=sa.Text(), nullable=True)
        batch.add_column(sa.Column(
            "subject_match",
            sa.String(200),
            nullable=False,
            server_default="",
        ))


def downgrade() -> None:
    with op.batch_alter_table("alert") as batch:
        batch.drop_column("subject_match")
        batch.alter_column("feed_url", existing_type=sa.Text(), nullable=False)
        batch.create_unique_constraint("uq_alert_feed_url", ["feed_url"])
