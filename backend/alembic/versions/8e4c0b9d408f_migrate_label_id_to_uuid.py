"""migrate label_id to uuid

Revision ID: 8e4c0b9d408f
Revises: 16e5b3ec4509
Create Date: 2026-03-22 04:09:33.716475+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8e4c0b9d408f'
down_revision = '16e5b3ec4509'
branch_labels = None
depends_on = None


def upgrade():
    # --- 1. drop PK ---

    op.drop_constraint('labels_pkey', 'labels', type_='primary')

    # --- 2. add UUID column, populate, swap ---

    op.add_column('labels', sa.Column('label_uuid', sa.UUID(), nullable=True))
    op.execute("UPDATE labels SET label_uuid = gen_random_uuid()")
    op.drop_column('labels', 'label_id')
    op.alter_column('labels', 'label_uuid', new_column_name='label_id', nullable=False)

    # --- 3. recreate PK ---

    op.create_primary_key('labels_pkey', 'labels', ['label_id'])


def downgrade():
    op.drop_constraint('labels_pkey', 'labels', type_='primary')

    op.add_column('labels', sa.Column('label_id_int', sa.INTEGER(), autoincrement=True, nullable=True))
    op.execute("CREATE SEQUENCE labels_label_id_seq_downgrade")
    op.execute("UPDATE labels SET label_id_int = nextval('labels_label_id_seq_downgrade')")
    op.drop_column('labels', 'label_id')
    op.alter_column('labels', 'label_id_int', new_column_name='label_id', nullable=False)

    op.execute("ALTER SEQUENCE labels_label_id_seq_downgrade OWNED BY labels.label_id")
    op.execute("ALTER TABLE labels ALTER COLUMN label_id SET DEFAULT nextval('labels_label_id_seq_downgrade')")

    op.create_primary_key('labels_pkey', 'labels', ['label_id'])
