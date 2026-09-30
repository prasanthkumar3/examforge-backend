import uuid

from sqlalchemy import String, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class QuestionOption(Base):
    __tablename__ = "question_options"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    option_text: Mapped[str] = mapped_column(
        String(1000),
        nullable=False
    )

    is_correct: Mapped[bool] = mapped_column(
        nullable=False,
        default=False
    )

    option_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )