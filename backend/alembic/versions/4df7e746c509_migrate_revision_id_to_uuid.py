"""migrate revision id to uuid

Revision ID: 4df7e746c509
Revises: 5619f067b676
Create Date: 2026-03-22 03:53:42.706392+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4df7e746c509'
down_revision = '5619f067b676'
branch_labels = None
depends_on = None


def upgrade():
    # --- 1. drop FK constraints referencing revisions.revision_id ---

    op.drop_constraint('fk_revision_texts_revision_id_revisions', 'revision_texts', type_='foreignkey')

    # --- 2. drop unique constraints that include revision_id ---

    op.drop_constraint('uq_revision_text_version_per_revision', 'revision_texts', type_='unique')

    # --- 3. drop PK on revisions ---

    op.drop_constraint('revisions_pkey', 'revisions', type_='primary')

    # --- 4. add new UUID columns ---

    op.add_column('revisions', sa.Column('revision_uuid', sa.UUID(), nullable=True))
    op.add_column('revision_texts', sa.Column('revision_uuid', sa.UUID(), nullable=True))

    # --- 5. populate UUIDs ---

    op.execute("UPDATE revisions SET revision_uuid = gen_random_uuid()")

    op.execute("""
        UPDATE revision_texts
        SET revision_uuid = r.revision_uuid
        FROM revisions r
        WHERE revision_texts.revision_id = r.revision_id
    """)

    # --- 6. drop old int columns, rename new columns ---

    op.drop_column('revision_texts', 'revision_id')
    op.drop_column('revisions', 'revision_id')

    op.alter_column('revisions', 'revision_uuid', new_column_name='revision_id', nullable=False)
    op.alter_column('revision_texts', 'revision_uuid', new_column_name='revision_id', nullable=False)

    # --- 7. recreate PK, FK, and unique constraints ---

    op.create_primary_key('revisions_pkey', 'revisions', ['revision_id'])

    op.create_foreign_key('fk_revision_texts_revision_id_revisions', 'revision_texts', 'revisions', ['revision_id'], ['revision_id'])

    op.create_unique_constraint('uq_revision_text_version_per_revision', 'revision_texts', ['revision_id', 'revision_text_version'])


def downgrade():
    op.drop_constraint('uq_revision_text_version_per_revision', 'revision_texts', type_='unique')
    op.drop_constraint('fk_revision_texts_revision_id_revisions', 'revision_texts', type_='foreignkey')
    op.drop_constraint('revisions_pkey', 'revisions', type_='primary')

    op.add_column('revisions', sa.Column('revision_id_int', sa.INTEGER(), autoincrement=True, nullable=True))
    op.add_column('revision_texts', sa.Column('revision_id_int', sa.INTEGER(), nullable=True))

    op.execute("CREATE SEQUENCE revisions_revision_id_seq_downgrade")
    op.execute("UPDATE revisions SET revision_id_int = nextval('revisions_revision_id_seq_downgrade')")

    op.execute("""
        UPDATE revision_texts
        SET revision_id_int = r.revision_id_int
        FROM revisions r
        WHERE revision_texts.revision_id = r.revision_id
    """)

    op.drop_column('revision_texts', 'revision_id')
    op.drop_column('revisions', 'revision_id')

    op.alter_column('revisions', 'revision_id_int', new_column_name='revision_id', nullable=False)
    op.alter_column('revision_texts', 'revision_id_int', new_column_name='revision_id', nullable=False)

    op.execute("ALTER SEQUENCE revisions_revision_id_seq_downgrade OWNED BY revisions.revision_id")
    op.execute("ALTER TABLE revisions ALTER COLUMN revision_id SET DEFAULT nextval('revisions_revision_id_seq_downgrade')")

    op.create_primary_key('revisions_pkey', 'revisions', ['revision_id'])
    op.create_foreign_key('fk_revision_texts_revision_id_revisions', 'revision_texts', 'revisions', ['revision_id'], ['revision_id'])
    op.create_unique_constraint('uq_revision_text_version_per_revision', 'revision_texts', ['revision_id', 'revision_text_version'])
