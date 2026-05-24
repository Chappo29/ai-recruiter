"""add candidate_reminders table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-24 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "candidate_reminders",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("telegram_id", sa.String(64), nullable=False),
        sa.Column("agency_id", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("vacancy_title", sa.String(255), nullable=False),
        sa.Column("screening_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reminded_at_first", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("reminded_at_24h", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("cancelled", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_index(
        "ix_candidate_reminders_telegram_id",
        "candidate_reminders",
        ["telegram_id"],
    )
    op.create_index(
        "ix_candidate_reminders_cancelled",
        "candidate_reminders",
        ["cancelled"],
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_reminders_cancelled", table_name="candidate_reminders")
    op.drop_index("ix_candidate_reminders_telegram_id", table_name="candidate_reminders")
    op.drop_table("candidate_reminders")
