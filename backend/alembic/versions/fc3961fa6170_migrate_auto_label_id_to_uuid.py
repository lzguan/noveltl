"""migrate auto_label_id to uuid

Revision ID: fc3961fa6170
Revises: 8e4c0b9d408f
Create Date: 2026-03-22 04:12:12.184221+00:00

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "fc3961fa6170"
down_revision = "8e4c0b9d408f"
branch_labels = None
depends_on = None


def upgrade():
    # --- 1. drop PK ---

    op.drop_constraint("auto_labels_pkey", "auto_labels", type_="primary")

    # --- 2. add UUID column, populate, swap ---

    op.add_column("auto_labels", sa.Column("auto_label_uuid", sa.UUID(), nullable=True))
    op.execute("UPDATE auto_labels SET auto_label_uuid = gen_random_uuid()")
    op.drop_column("auto_labels", "auto_label_id")
    op.alter_column("auto_labels", "auto_label_uuid", new_column_name="auto_label_id", nullable=False)

    # --- 3. recreate PK ---

    op.create_primary_key("auto_labels_pkey", "auto_labels", ["auto_label_id"])


def downgrade():
    op.drop_constraint("auto_labels_pkey", "auto_labels", type_="primary")

    op.add_column("auto_labels", sa.Column("auto_label_id_int", sa.INTEGER(), autoincrement=True, nullable=True))
    op.execute("CREATE SEQUENCE auto_labels_auto_label_id_seq_downgrade")
    op.execute("UPDATE auto_labels SET auto_label_id_int = nextval('auto_labels_auto_label_id_seq_downgrade')")
    op.drop_column("auto_labels", "auto_label_id")
    op.alter_column("auto_labels", "auto_label_id_int", new_column_name="auto_label_id", nullable=False)

    op.execute("ALTER SEQUENCE auto_labels_auto_label_id_seq_downgrade OWNED BY auto_labels.auto_label_id")
    op.execute(
        "ALTER TABLE auto_labels ALTER COLUMN auto_label_id SET DEFAULT nextval('auto_labels_auto_label_id_seq_downgrade')"
    )

    op.create_primary_key("auto_labels_pkey", "auto_labels", ["auto_label_id"])
