"""create exam attempt tables

Revision ID: c7e91a4b2d11
Revises: 1cb2c2002cde
Create Date: 2026-09-28

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c7e91a4b2d11"
down_revision: Union[str, Sequence[str], None] = "1cb2c2002cde"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create exam_attempts and attempt_answers tables."""

    op.create_table(
        "exam_attempts",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "exam_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),

        sa.Column(
            "access_method",
            sa.String(length=20),
            nullable=False,
        ),

        sa.Column(
            "candidate_name",
            sa.String(length=150),
            nullable=True,
        ),

        sa.Column(
            "candidate_email",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "attempt_number",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
        ),

        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "score",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        sa.CheckConstraint(
            "access_method IN ('BATCH', 'ROOM_CODE')",
            name="check_exam_attempt_access_method",
        ),

        sa.CheckConstraint(
            "status IN ('IN_PROGRESS', 'SUBMITTED', 'EXPIRED')",
            name="check_exam_attempt_status",
        ),

        sa.ForeignKeyConstraint(
            ["exam_id"],
            ["exams.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),

        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_exam_attempts_exam_id",
        "exam_attempts",
        ["exam_id"],
        unique=False,
    )

    op.create_index(
        "ix_exam_attempts_user_id",
        "exam_attempts",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "attempt_answers",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "attempt_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "selected_option_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
        ),

        sa.Column(
            "answered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["exam_attempts.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint(
            "attempt_id",
            "question_id",
            name="uq_attempt_answer",
        ),
    )

    op.create_index(
        "ix_attempt_answers_attempt_id",
        "attempt_answers",
        ["attempt_id"],
        unique=False,
    )

    op.create_index(
        "ix_attempt_answers_question_id",
        "attempt_answers",
        ["question_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop exam attempt tables."""

    op.drop_index(
        "ix_attempt_answers_question_id",
        table_name="attempt_answers",
    )

    op.drop_index(
        "ix_attempt_answers_attempt_id",
        table_name="attempt_answers",
    )

    op.drop_table("attempt_answers")

    op.drop_index(
        "ix_exam_attempts_user_id",
        table_name="exam_attempts",
    )

    op.drop_index(
        "ix_exam_attempts_exam_id",
        table_name="exam_attempts",
    )

    op.drop_table("exam_attempts")