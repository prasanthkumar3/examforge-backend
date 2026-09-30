import uuid

from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    question_text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    question_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    topic: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    difficulty: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="MEDIUM"
    )

    explanation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    marks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1
    )

    negative_marks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="DRAFT"
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