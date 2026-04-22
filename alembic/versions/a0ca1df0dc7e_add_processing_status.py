"""add_processing_status

Revision ID: a0ca1df0dc7e
Revises: 0235ff20694c
Create Date: 2026-04-21 21:09:12.510189

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a0ca1df0dc7e'
down_revision: Union[str, Sequence[str], None] = '0235ff20694c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE status ADD VALUE IF NOT EXISTS 'processing' AFTER 'new'")


def downgrade() -> None:
    # Postgres does not support removing enum values; downgrade is a no-op
    pass
