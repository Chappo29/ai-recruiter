"""add company to vacancies

Revision ID: a1b2c3d4e5f6
Revises: 7a6b83b8fd84
Create Date: 2026-05-23 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "7a6b83b8fd84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("vacancies", sa.Column("company", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("vacancies", "company")
