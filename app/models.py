import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Agency(Base):
    __tablename__ = "agencies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(String(32), nullable=False, default="free")
    telegram_bot_token: Mapped[str | None] = mapped_column(
        String, nullable=True, unique=True
    )
    feedback_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default="3"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    users: Mapped[list["User"]] = relationship(back_populates="agency")

    def __repr__(self) -> str:
        return f"<Agency id={self.id!s} name={self.name!r} plan={self.plan!r}>"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="recruiter")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    agency: Mapped["Agency"] = relationship(back_populates="users")
    vacancies: Mapped[list["Vacancy"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id!s} email={self.email!r} role={self.role!r}>"


class Vacancy(Base):
    __tablename__ = "vacancies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    hh_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="vacancies")
    screenings: Mapped[list["Screening"]] = relationship(back_populates="vacancy")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="vacancy", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Vacancy id={self.id!s} title={self.title!r} status={self.status!r}>"


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    telegram_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    hh_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    resume_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resume_file_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    screenings: Mapped[list["Screening"]] = relationship(back_populates="candidate")

    def __repr__(self) -> str:
        return (
            f"<Candidate id={self.id!s} full_name={self.full_name!r} "
            f"telegram_id={self.telegram_id!r}>"
        )


class Screening(Base):
    __tablename__ = "screenings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vacancies.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    verdict: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    score: Mapped[Optional[int]] = mapped_column(nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_markers: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dialog_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    vacancy: Mapped["Vacancy"] = relationship(back_populates="screenings")
    candidate: Mapped["Candidate"] = relationship(back_populates="screenings")
    candidate_answers: Mapped[list["CandidateAnswer"]] = relationship(
        back_populates="screening", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Screening id={self.id!s} vacancy_id={self.vacancy_id!s} "
            f"candidate_id={self.candidate_id!s} status={self.status!r} "
            f"verdict={self.verdict!r}>"
        )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vacancies.id", ondelete="CASCADE"),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    vacancy: Mapped["Vacancy"] = relationship(back_populates="questions")
    candidate_answers: Mapped[list["CandidateAnswer"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Question id={self.id!s} vacancy_id={self.vacancy_id!s} order_index={self.order_index}>"


class CandidateAnswer(Base):
    __tablename__ = "candidate_answers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    screening_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("screenings.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    answer_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    screening: Mapped["Screening"] = relationship(back_populates="candidate_answers")
    question: Mapped["Question"] = relationship(back_populates="candidate_answers")

    def __repr__(self) -> str:
        return (
            f"<CandidateAnswer id={self.id!s} screening_id={self.screening_id!s} "
            f"question_id={self.question_id!s}>"
        )


class CandidateReminder(Base):
    """Tracks abandonment reminders for candidates mid-flow."""

    __tablename__ = "candidate_reminders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    telegram_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    agency_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # "waiting_resume" (State A) | "waiting_answers" (State B)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    vacancy_title: Mapped[str] = mapped_column(String(255), nullable=False)
    screening_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # State A: first reminder at 4h; State B: first reminder at 2h
    reminded_at_first: Mapped[bool] = mapped_column(default=False, server_default="false")
    reminded_at_24h: Mapped[bool] = mapped_column(default=False, server_default="false")
    cancelled: Mapped[bool] = mapped_column(default=False, server_default="false", index=True)

    def __repr__(self) -> str:
        return (
            f"<CandidateReminder id={self.id!s} telegram_id={self.telegram_id!r} "
            f"state={self.state!r} cancelled={self.cancelled}>"
        )
