"""add_bot_token_to_agencies

Revision ID: 002_add_bot_token
Revises: 001_initial
Create Date: 2026-05-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_add_bot_token"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agencies",
        sa.Column("telegram_bot_token", sa.String(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_agencies_telegram_bot_token",
        "agencies",
        ["telegram_bot_token"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_agencies_telegram_bot_token", "agencies", type_="unique")
    op.drop_column("agencies", "telegram_bot_token")
