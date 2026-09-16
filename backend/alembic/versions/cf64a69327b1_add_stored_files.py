"""add stored files

Revision ID: cf64a69327b1
Revises: b7e4c9d1a6f2
Create Date: 2026-09-12 00:00:00+00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "cf64a69327b1"
down_revision = "b7e4c9d1a6f2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stored_files",
        sa.Column("file_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("storage_name", sa.String(length=32), nullable=False),
        sa.Column("bucket", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("content_encoding", sa.String(length=64), nullable=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("etag", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("byte_size >= 0", name="ck_stored_files_byte_size"),
        sa.PrimaryKeyConstraint("file_id"),
        sa.UniqueConstraint("storage_name", "bucket", "object_key", name="uq_stored_files_location"),
    )


def downgrade():
    op.drop_table("stored_files")
