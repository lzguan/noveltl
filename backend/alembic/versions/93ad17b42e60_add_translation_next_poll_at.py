"""Add the translation polling deadline.

Revision ID: 93ad17b42e60
Revises: aa638b86e216
"""

import sqlalchemy as sa

from alembic import op

revision = "93ad17b42e60"
down_revision = "aa638b86e216"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("translation_tasks", sa.Column("next_poll_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("translation_tasks", "next_poll_at")
