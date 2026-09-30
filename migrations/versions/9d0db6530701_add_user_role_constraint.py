"""add user role constraint

Revision ID: 9d0db6530701
Revises: af2ca9783edf
Create Date: 2026-09-27 14:10:35.223428

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d0db6530701'
down_revision: Union[str, Sequence[str], None] = 'af2ca9783edf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "check_user_role",
        "users",
        "role IN ('ADMIN', 'EXAMINER', 'STUDENT')"
    )


def downgrade() -> None:
    op.drop_constraint(
        "check_user_role",
        "users",
        type_="check"
    )