"""add memory mark

Revision ID: a418f1dd30cb
Revises: 61d8d246e12a
Create Date: 2026-08-30 05:00:00+00:00

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "a418f1dd30cb"
down_revision = "61d8d246e12a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("memories", sa.Column("mark", sa.String(), nullable=True))


def downgrade():
    op.drop_column("memories", "mark")
