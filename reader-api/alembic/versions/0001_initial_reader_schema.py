"""initial reader schema

Revision ID: 0001_initial_reader_schema
Revises:
Create Date: 2026-11-25 06:00:00.000000+00:00

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_initial_reader_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reader_partners",
        sa.Column(
            "partner_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("partner_id"),
    )

    op.create_table(
        "reader_partner_keys",
        sa.Column(
            "key_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["partner_id"], ["reader_partners.partner_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("key_id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index(op.f("ix_reader_partner_keys_partner_id"), "reader_partner_keys", ["partner_id"], unique=False)

    op.create_table(
        "reader_novels",
        sa.Column(
            "novel_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("language_code", sa.String(length=32), server_default="en", nullable=False),
        sa.Column("toc_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["partner_id"], ["reader_partners.partner_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("novel_id"),
        sa.UniqueConstraint("partner_id", "external_id", name="uq_reader_novels_partner_external_id"),
    )
    op.create_index(op.f("ix_reader_novels_partner_id"), "reader_novels", ["partner_id"], unique=False)

    op.create_table(
        "reader_chapters",
        sa.Column(
            "chapter_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("novel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_num", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("external_version", sa.String(length=128), nullable=True),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["novel_id"], ["reader_novels.novel_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chapter_id"),
        sa.UniqueConstraint("novel_id", "chapter_num", name="uq_reader_chapters_novel_chapter_num"),
    )
    op.create_index(op.f("ix_reader_chapters_novel_id"), "reader_chapters", ["novel_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_reader_chapters_novel_id"), table_name="reader_chapters")
    op.drop_table("reader_chapters")
    op.drop_index(op.f("ix_reader_novels_partner_id"), table_name="reader_novels")
    op.drop_table("reader_novels")
    op.drop_index(op.f("ix_reader_partner_keys_partner_id"), table_name="reader_partner_keys")
    op.drop_table("reader_partner_keys")
    op.drop_table("reader_partners")
