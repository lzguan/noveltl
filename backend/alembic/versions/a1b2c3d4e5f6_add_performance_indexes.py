"""add performance indexes

Revision ID: a1b2c3d4e5f6
Revises: 06741dac5042
Create Date: 2026-03-06 00:00:00.000000+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '06741dac5042'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_raw_chapter_num', 'raw_chapters', ['raw_chapter_num'])
    op.create_index('ix_novel_contributors_user_id', 'novel_contributors', ['user_id'])
    op.create_index('ix_label_group_contributors_user_id', 'label_group_contributors', ['user_id'])


def downgrade():
    op.drop_index('ix_label_group_contributors_user_id', table_name='label_group_contributors')
    op.drop_index('ix_novel_contributors_user_id', table_name='novel_contributors')
    op.drop_index('ix_raw_chapter_num', table_name='raw_chapters')
