"""add continuity summaries

Revision ID: b7e4c9d1a6f2
Revises: a418f1dd30cb
Create Date: 2026-09-07 00:00:00+00:00
"""

from alembic import op

revision = "b7e4c9d1a6f2"
down_revision = "a418f1dd30cb"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "uq_continuity_summary_group_content",
        "memories",
        ["memory_group_id", "memory_observed_in"],
        unique=True,
        postgresql_where="memory_type = 'summary' AND plugin_name = 'continuity'",
    )


def downgrade():
    op.drop_index("uq_continuity_summary_group_content", table_name="memories")
