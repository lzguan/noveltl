"""add translation chapter outputs, accepts, and job chapter_num

Revision ID: e3f8b1c4a7d2
Revises: d7e2a94c1b51
Create Date: 2026-11-25 04:42:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e3f8b1c4a7d2"
down_revision: str | Sequence[str] | None = "d7e2a94c1b51"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("translation_job_chapters", sa.Column("chapter_num", sa.Integer(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE translation_job_chapters tjc "
            "SET chapter_num = c.chapter_num "
            "FROM chapters c "
            "WHERE c.chapter_id = tjc.chapter_id"
        )
    )
    op.alter_column("translation_job_chapters", "chapter_num", nullable=False)

    op.create_unique_constraint(
        "uq_translation_stage_id_job_id",
        "translation_stages",
        ["stage_id", "job_id"],
    )

    op.create_table(
        "translation_chapter_outputs",
        sa.Column("stage_id", sa.UUID(), nullable=False),
        sa.Column("chapter_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("translated_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["stage_id", "job_id"],
            ["translation_stages.stage_id", "translation_stages.job_id"],
            name="fk_translation_chapter_outputs_stage_job",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "chapter_id"],
            ["translation_job_chapters.job_id", "translation_job_chapters.chapter_id"],
            name="fk_translation_chapter_outputs_job_chapter",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("stage_id", "chapter_id"),
    )
    op.create_index(
        op.f("ix_translation_chapter_outputs_job_id"),
        "translation_chapter_outputs",
        ["job_id"],
        unique=False,
    )

    op.create_table(
        "translation_chapter_accepts",
        sa.Column("accept_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("stage_id", sa.UUID(), nullable=False),
        sa.Column("source_chapter_id", sa.UUID(), nullable=False),
        sa.Column("target_chapter_content_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["stage_id", "source_chapter_id"],
            ["translation_chapter_outputs.stage_id", "translation_chapter_outputs.chapter_id"],
            name="fk_translation_chapter_accepts_output",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_chapter_content_id"],
            ["chapter_contents.chapter_content_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("accept_id"),
    )
    op.create_index(
        op.f("ix_translation_chapter_accepts_target_chapter_content_id"),
        "translation_chapter_accepts",
        ["target_chapter_content_id"],
        unique=False,
    )
    op.create_index(
        "ix_translation_chapter_accepts_stage_source",
        "translation_chapter_accepts",
        ["stage_id", "source_chapter_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_translation_chapter_accepts_stage_source", table_name="translation_chapter_accepts")
    op.drop_index(
        op.f("ix_translation_chapter_accepts_target_chapter_content_id"),
        table_name="translation_chapter_accepts",
    )
    op.drop_table("translation_chapter_accepts")
    op.drop_index(
        op.f("ix_translation_chapter_outputs_job_id"),
        table_name="translation_chapter_outputs",
    )
    op.drop_table("translation_chapter_outputs")
    op.drop_constraint("uq_translation_stage_id_job_id", "translation_stages", type_="unique")
    op.drop_column("translation_job_chapters", "chapter_num")
