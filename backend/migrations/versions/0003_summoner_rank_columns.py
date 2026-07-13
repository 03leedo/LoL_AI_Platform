"""Add solo-queue rank columns to summoners.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("summoners", sa.Column("solo_tier", sa.String(length=16), nullable=True))
    op.add_column("summoners", sa.Column("solo_division", sa.String(length=8), nullable=True))
    op.add_column("summoners", sa.Column("solo_lp", sa.Integer(), nullable=True))
    op.add_column("summoners", sa.Column("solo_wins", sa.Integer(), nullable=True))
    op.add_column("summoners", sa.Column("solo_losses", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("summoners", "solo_losses")
    op.drop_column("summoners", "solo_wins")
    op.drop_column("summoners", "solo_lp")
    op.drop_column("summoners", "solo_division")
    op.drop_column("summoners", "solo_tier")
