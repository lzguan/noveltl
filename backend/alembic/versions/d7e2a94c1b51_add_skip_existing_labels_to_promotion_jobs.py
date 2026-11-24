"""add skip_existing_labels to label_promotion_jobs

Revision ID: d7e2a94c1b51
Revises: c2b4f81a9d30
Create Date: 2026-11-24 09:46:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d7e2a94c1b51"
down_revision: str | Sequence[str] | None = "c2b4f81a9d30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "label_promotion_jobs",
        sa.Column("skip_existing_labels", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_column("label_promotion_jobs", "skip_existing_labels")
