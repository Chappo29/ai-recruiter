"""drop unique constraint on candidates.telegram_id

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-05-27 14:00:00.000000

"""
from alembic import op

revision = "e3f4a5b6c7d8"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("candidates_telegram_id_key", "candidates", type_="unique")
    op.create_index(
        op.f("ix_candidates_telegram_id"),
        "candidates",
        ["telegram_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_candidates_telegram_id"), table_name="candidates")
    op.create_unique_constraint(
        "candidates_telegram_id_key", "candidates", ["telegram_id"]
    )
