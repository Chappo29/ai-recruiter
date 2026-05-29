"""add interview questions and answers tables

Revision ID: i3j4k5l6m7n8
Revises: h2i3j4k5l6m7
Create Date: 2026-05-27 18:02:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "i3j4k5l6m7n8"
down_revision = "h2i3j4k5l6m7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vacancy_interview_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vacancy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rubric_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("competency_id", sa.String(length=64), nullable=True),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("required", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="rubric"),
        sa.ForeignKeyConstraint(["rubric_id"], ["vacancy_rubrics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_vacancy_interview_questions_vacancy_id"),
        "vacancy_interview_questions",
        ["vacancy_id"],
        unique=False,
    )

    op.create_table(
        "interview_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("screening_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("score_1_5", sa.Integer(), nullable=True),
        sa.Column("evidence_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["question_id"], ["vacancy_interview_questions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["screening_id"], ["screenings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_interview_answers_screening_id"),
        "interview_answers",
        ["screening_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_interview_answers_screening_id"), table_name="interview_answers")
    op.drop_table("interview_answers")
    op.drop_index(
        op.f("ix_vacancy_interview_questions_vacancy_id"),
        table_name="vacancy_interview_questions",
    )
    op.drop_table("vacancy_interview_questions")
