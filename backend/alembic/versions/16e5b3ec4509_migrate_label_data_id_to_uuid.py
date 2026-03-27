"""migrate label_data_id to uuid

Revision ID: 16e5b3ec4509
Revises: 48dea3009a6f
Create Date: 2026-03-22 04:03:46.872163+00:00

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '16e5b3ec4509'
down_revision = '48dea3009a6f'
branch_labels = None
depends_on = None


def upgrade():
    # --- 1. drop FK constraints referencing label_datas.label_data_id ---

    op.drop_constraint('fk_labels_label_data_id_label_datas', 'labels', type_='foreignkey')

    # --- 2. drop exclusion constraint on labels (references label_data_id) ---

    op.execute("ALTER TABLE labels DROP CONSTRAINT no_overlapping_labels_per_group")

    # --- 3. drop PK on label_datas ---

    op.drop_constraint('label_datas_pkey', 'label_datas', type_='primary')

    # --- 4. add new UUID columns ---

    op.add_column('label_datas', sa.Column('label_data_uuid', sa.UUID(), nullable=True))
    op.add_column('labels', sa.Column('label_data_uuid', sa.UUID(), nullable=True))

    # --- 5. populate UUIDs ---

    op.execute("UPDATE label_datas SET label_data_uuid = gen_random_uuid()")

    op.execute("""
        UPDATE labels
        SET label_data_uuid = ld.label_data_uuid
        FROM label_datas ld
        WHERE labels.label_data_id = ld.label_data_id
    """)

    # --- 6. drop old int columns, rename new columns ---

    op.drop_column('labels', 'label_data_id')
    op.drop_column('label_datas', 'label_data_id')

    op.alter_column('label_datas', 'label_data_uuid', new_column_name='label_data_id', nullable=False)
    op.alter_column('labels', 'label_data_uuid', new_column_name='label_data_id', nullable=False)

    # --- 7. recreate PK, FK, and exclusion constraint ---

    op.create_primary_key('label_datas_pkey', 'label_datas', ['label_data_id'])

    op.create_foreign_key('fk_labels_label_data_id_label_datas', 'labels', 'label_datas', ['label_data_id'], ['label_data_id'])

    op.execute("""
        ALTER TABLE labels ADD CONSTRAINT no_overlapping_labels_per_group
        EXCLUDE USING gist (label_data_id WITH =, int4range(label_start, label_end, '[)') WITH &&)
    """)


def downgrade():
    op.execute("ALTER TABLE labels DROP CONSTRAINT no_overlapping_labels_per_group")
    op.drop_constraint('fk_labels_label_data_id_label_datas', 'labels', type_='foreignkey')
    op.drop_constraint('label_datas_pkey', 'label_datas', type_='primary')

    op.add_column('label_datas', sa.Column('label_data_id_int', sa.INTEGER(), autoincrement=True, nullable=True))
    op.add_column('labels', sa.Column('label_data_id_int', sa.INTEGER(), nullable=True))

    op.execute("CREATE SEQUENCE label_datas_label_data_id_seq_downgrade")
    op.execute("UPDATE label_datas SET label_data_id_int = nextval('label_datas_label_data_id_seq_downgrade')")

    op.execute("""
        UPDATE labels
        SET label_data_id_int = ld.label_data_id_int
        FROM label_datas ld
        WHERE labels.label_data_id = ld.label_data_id
    """)

    op.drop_column('labels', 'label_data_id')
    op.drop_column('label_datas', 'label_data_id')

    op.alter_column('label_datas', 'label_data_id_int', new_column_name='label_data_id', nullable=False)
    op.alter_column('labels', 'label_data_id_int', new_column_name='label_data_id', nullable=False)

    op.execute("ALTER SEQUENCE label_datas_label_data_id_seq_downgrade OWNED BY label_datas.label_data_id")
    op.execute("ALTER TABLE label_datas ALTER COLUMN label_data_id SET DEFAULT nextval('label_datas_label_data_id_seq_downgrade')")

    op.create_primary_key('label_datas_pkey', 'label_datas', ['label_data_id'])
    op.create_foreign_key('fk_labels_label_data_id_label_datas', 'labels', 'label_datas', ['label_data_id'], ['label_data_id'])

    op.execute("""
        ALTER TABLE labels ADD CONSTRAINT no_overlapping_labels_per_group
        EXCLUDE USING gist (label_data_id WITH =, int4range(label_start, label_end, '[)') WITH &&)
    """)
