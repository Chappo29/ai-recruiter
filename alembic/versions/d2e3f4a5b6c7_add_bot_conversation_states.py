"""add bot_conversation_states

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-05-27 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bot_conversation_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("telegram_id", sa.String(length=64), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step", sa.String(length=32), nullable=False),
        sa.Column("state_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id", "agency_id", name="uq_bot_state_telegram_agency"),
    )
    op.create_index(
        op.f("ix_bot_conversation_states_agency_id"),
        "bot_conversation_states",
        ["agency_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bot_conversation_states_telegram_id"),
        "bot_conversation_states",
        ["telegram_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_bot_conversation_states_telegram_id"),
        table_name="bot_conversation_states",
    )
    op.drop_index(
        op.f("ix_bot_conversation_states_agency_id"),
        table_name="bot_conversation_states",
    )
    op.drop_table("bot_conversation_states")
