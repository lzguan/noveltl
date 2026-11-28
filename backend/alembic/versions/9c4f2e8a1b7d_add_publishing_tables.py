"""add publishing targets and jobs

Revision ID: 9c4f2e8a1b7d
Revises: e3f8b1c4a7d2
Create Date: 2026-11-27 06:25:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9c4f2e8a1b7d"
down_revision: str | Sequence[str] | None = "e3f8b1c4a7d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "publishing_targets",
        sa.Column("target_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("api_base_url", sa.Text(), nullable=False),
        sa.Column("public_base_url", sa.Text(), nullable=True),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("key_prefix", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.user_id"],
            name="fk_publishing_targets_created_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("target_id"),
    )

    op.create_table(
        "user_publishing_targets",
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('owner', 'publisher')", name="ck_user_publishing_targets_role"),
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["publishing_targets.target_id"],
            name="fk_user_publishing_targets_target_id_publishing_targets",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name="fk_user_publishing_targets_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("target_id", "user_id"),
    )
    op.create_index("ix_user_publishing_targets_user_id", "user_publishing_targets", ["user_id"], unique=False)

    op.create_table(
        "publish_jobs",
        sa.Column("job_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("novel_id", sa.UUID(), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("initiated_by_user_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("start_chapter", sa.Integer(), nullable=True),
        sa.Column("end_chapter", sa.Integer(), nullable=True),
        sa.Column("include_novel_metadata", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("cursor_chapter_num", sa.Integer(), nullable=True),
        sa.Column("total_chapters", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("synced_chapters", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("reader_novel_id", sa.UUID(), nullable=True),
        sa.Column("public_url", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_publish_jobs_status",
        ),
        sa.CheckConstraint("mode IN ('all', 'outdated', 'range')", name="ck_publish_jobs_mode"),
        sa.ForeignKeyConstraint(
            ["initiated_by_user_id"],
            ["users.user_id"],
            name="fk_publish_jobs_initiated_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["novel_id"],
            ["novels.novel_id"],
            name="fk_publish_jobs_novel_id_novels",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["publishing_targets.target_id"],
            name="fk_publish_jobs_target_id_publishing_targets",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index(
        "uq_publish_jobs_active_novel_target",
        "publish_jobs",
        ["novel_id", "target_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'processing')"),
    )
    op.create_index("ix_publish_jobs_novel_id_created_at", "publish_jobs", ["novel_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_publish_jobs_novel_id_created_at", table_name="publish_jobs")
    op.drop_index(
        "uq_publish_jobs_active_novel_target",
        table_name="publish_jobs",
        postgresql_where=sa.text("status IN ('pending', 'processing')"),
    )
    op.drop_table("publish_jobs")
    op.drop_index("ix_user_publishing_targets_user_id", table_name="user_publishing_targets")
    op.drop_table("user_publishing_targets")
    op.drop_table("publishing_targets")
