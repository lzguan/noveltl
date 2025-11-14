"""add check constraint for raw chapter revisions

Revision ID: c0ef1ad0c0c8
Revises: dd70ca7f7dcd
Create Date: 2025-11-14 08:50:17.910744+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c0ef1ad0c0c8'
down_revision = 'dd70ca7f7dcd'
branch_labels = None
depends_on = None


def upgrade():
    op.create_check_constraint("primary_must_be_public_check", "raw_chapter_revisions", "raw_chapter_revision_is_public IS TRUE OR raw_chapter_revision_is_primary IS FALSE")


def downgrade():
    op.drop_constraint("primary_must_be_public_check", "raw_chapter_revisions")
