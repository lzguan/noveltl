import sqlalchemy as sa

from alembic import op

revision = "a9d3e7c1b2f4"
down_revision = "f8b2c4d6e901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The loader stage's output file replaced the per-batch snapshot.
    op.drop_column("translation_batches", "initial_file_id")
    # The file holds the provider request, not the task's pipeline input.
    op.alter_column("translation_tasks", "input_file_id", new_column_name="request_file_id")


def downgrade() -> None:
    op.alter_column("translation_tasks", "request_file_id", new_column_name="input_file_id")
    op.add_column("translation_batches", sa.Column("initial_file_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "translation_batches_initial_file_id_fkey",
        "translation_batches",
        "stored_files",
        ["initial_file_id"],
        ["file_id"],
    )
