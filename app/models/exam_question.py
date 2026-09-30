import uuid

from sqlalchemy import ForeignKey, Integer, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    __table_args__ = (
    UniqueConstraint(
        "exam_id",
        "question_id",
        name="uq_exam_question"
    ),
    UniqueConstraint(
        "exam_id",
        "question_order",
        name="uq_exam_question_order"
    ),
    CheckConstraint(
        "marks > 0",
        name="check_exam_question_marks"
    ),
    CheckConstraint(
        "negative_marks >= 0",
        name="check_exam_question_negative_marks"
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

    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    question_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False
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