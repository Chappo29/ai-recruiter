"""team invitations + candidate agency_id

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-05-27 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f4a5b6c7d8e9"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_candidates_agency_id",
        "candidates",
        "agencies",
        ["agency_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_candidates_agency_id"), "candidates", ["agency_id"], unique=False
    )

    # Backfill agency_id from latest screening's vacancy owner agency
    op.execute(
        """
        UPDATE candidates c
        SET agency_id = sub.agency_id
        FROM (
            SELECT DISTINCT ON (s.candidate_id)
                s.candidate_id,
                u.agency_id
            FROM screenings s
            JOIN vacancies v ON v.id = s.vacancy_id
            JOIN users u ON u.id = v.user_id
            ORDER BY s.candidate_id, s.created_at DESC
        ) sub
        WHERE c.id = sub.candidate_id AND c.agency_id IS NULL
        """
    )

    op.create_table(
        "team_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_team_invitations_agency_id"),
        "team_invitations",
        ["agency_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_team_invitations_email"), "team_invitations", ["email"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_team_invitations_email"), table_name="team_invitations")
    op.drop_index(op.f("ix_team_invitations_agency_id"), table_name="team_invitations")
    op.drop_table("team_invitations")
    op.drop_index(op.f("ix_candidates_agency_id"), table_name="candidates")
    op.drop_constraint("fk_candidates_agency_id", "candidates", type_="foreignkey")
    op.drop_column("candidates", "agency_id")
