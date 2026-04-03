"""add server default for uuid primary keys

Revision ID: e36f5285fe7c
Revises: fc3961fa6170
Create Date: 2026-03-28 01:28:50.949139+00:00

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "e36f5285fe7c"
down_revision = "fc3961fa6170"
branch_labels = None
depends_on = None

# All UUID primary key columns missing server_default=gen_random_uuid().
# revision_texts.revision_text_id already has it.
_TABLE_PK_PAIRS = [
    ("novels", "novel_id"),
    ("chapters", "chapter_id"),
    ("revisions", "revision_id"),
    ("label_groups", "label_group_id"),
    ("label_datas", "label_data_id"),
    ("labels", "label_id"),
    ("auto_labels", "auto_label_id"),
    ("users", "user_id"),
]


def upgrade():
    for table, column in _TABLE_PK_PAIRS:
        op.alter_column(table, column, server_default=sa.text("gen_random_uuid()"))


def downgrade():
    for table, column in _TABLE_PK_PAIRS:
        op.alter_column(table, column, server_default=None)
