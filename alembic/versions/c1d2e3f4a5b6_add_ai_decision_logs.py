"""add ai_decision_logs

Revision ID: c1d2e3f4a5b6
Revises: 9b8c74d3e5a1
Create Date: 2026-05-27 00:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "c1d2e3f4a5b6"
down_revision = "9b8c74d3e5a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_decision_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("screening_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision_type", sa.String(length=32), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False, server_default="ai"),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ai_score", sa.Integer(), nullable=True),
        sa.Column("ai_verdict", sa.String(length=32), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column(
            "human_override",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["screening_id"], ["screenings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ai_decision_logs_agency_id"),
        "ai_decision_logs",
        ["agency_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_decision_logs_screening_id"),
        "ai_decision_logs",
        ["screening_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_decision_logs_screening_id"), table_name="ai_decision_logs")
    op.drop_index(op.f("ix_ai_decision_logs_agency_id"), table_name="ai_decision_logs")
    op.drop_table("ai_decision_logs")
