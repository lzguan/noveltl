"""add reader feedback table

Revision ID: c7e3a1f94b21
Revises: b61e9b616936
Create Date: 2026-11-27 06:20:00.000000+00:00

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "c7e3a1f94b21"
down_revision = "b61e9b616936"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reader_feedback",
        sa.Column("feedback_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("novel_id", sa.UUID(), nullable=False),
        sa.Column("chapter_id", sa.UUID(), nullable=False),
        sa.Column("chapter_num", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("external_version", sa.Text(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("client_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["chapter_id"], ["reader_chapters.chapter_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["novel_id"], ["reader_novels.novel_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("feedback_id"),
    )
    op.create_index("ix_reader_feedback_created_id", "reader_feedback", ["created_at", "feedback_id"], unique=False)
    op.create_index(
        "ix_reader_feedback_novel_chapter_created",
        "reader_feedback",
        ["novel_id", "chapter_num", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_reader_feedback_novel_chapter_created", table_name="reader_feedback")
    op.drop_index("ix_reader_feedback_created_id", table_name="reader_feedback")
    op.drop_table("reader_feedback")
