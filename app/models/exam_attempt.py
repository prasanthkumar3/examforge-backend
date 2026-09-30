import uuid

from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    Integer,
    CheckConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    __table_args__ = (
        CheckConstraint(
            "access_method IN ('BATCH', 'ROOM_CODE')",
            name="check_exam_attempt_access_method"
        ),
        CheckConstraint(
            "status IN ('IN_PROGRESS', 'SUBMITTED', 'EXPIRED')",
            name="check_exam_attempt_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    exam_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    access_method: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    candidate_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    candidate_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="IN_PROGRESS"
    )

    started_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    submitted_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )