"""migrate chapter id to uuid

Revision ID: 5619f067b676
Revises: c97bd65993aa
Create Date: 2026-03-22 03:43:11.513422+00:00

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '5619f067b676'
down_revision = 'c97bd65993aa'
branch_labels = None
depends_on = None


def upgrade():
    # --- 1. drop FK constraints referencing chapters.chapter_id ---

    op.drop_constraint('fk_revisions_chapter_id_chapters', 'revisions', type_='foreignkey')

    # --- 2. drop indexes/constraints that include chapter_id ---

    op.drop_index('ix_one_primary_revision_per_chapter', 'revisions')

    # --- 3. drop PK on chapters ---

    op.drop_constraint('chapters_pkey', 'chapters', type_='primary')

    # --- 4. add new UUID columns ---

    op.add_column('chapters', sa.Column('chapter_uuid', sa.UUID(), nullable=True))
    op.add_column('revisions', sa.Column('chapter_uuid', sa.UUID(), nullable=True))

    # --- 5. populate UUIDs ---

    op.execute("UPDATE chapters SET chapter_uuid = gen_random_uuid()")

    op.execute("""
        UPDATE revisions
        SET chapter_uuid = c.chapter_uuid
        FROM chapters c
        WHERE revisions.chapter_id = c.chapter_id
    """)

    # --- 6. drop old int columns, rename new columns ---

    op.drop_column('revisions', 'chapter_id')
    op.drop_column('chapters', 'chapter_id')

    op.alter_column('chapters', 'chapter_uuid', new_column_name='chapter_id', nullable=False)
    op.alter_column('revisions', 'chapter_uuid', new_column_name='chapter_id', nullable=False)

    # --- 7. recreate PK, FK, and indexes ---

    op.create_primary_key('chapters_pkey', 'chapters', ['chapter_id'])

    op.create_foreign_key('fk_revisions_chapter_id_chapters', 'revisions', 'chapters', ['chapter_id'], ['chapter_id'])

    op.create_index(
        'ix_one_primary_revision_per_chapter', 'revisions', ['chapter_id'],
        unique=True, postgresql_where=sa.text('revision_is_primary IS TRUE')
    )


def downgrade():
    # --- 1. drop FK and indexes ---

    op.drop_index('ix_one_primary_revision_per_chapter', 'revisions')
    op.drop_constraint('fk_revisions_chapter_id_chapters', 'revisions', type_='foreignkey')
    op.drop_constraint('chapters_pkey', 'chapters', type_='primary')

    # --- 2. add old int columns ---

    op.add_column('chapters', sa.Column('chapter_id_int', sa.INTEGER(), autoincrement=True, nullable=True))
    op.add_column('revisions', sa.Column('chapter_id_int', sa.INTEGER(), nullable=True))

    # --- 3. populate with sequential IDs and copy mapping ---

    op.execute("CREATE SEQUENCE chapters_chapter_id_seq_downgrade")
    op.execute("UPDATE chapters SET chapter_id_int = nextval('chapters_chapter_id_seq_downgrade')")

    op.execute("""
        UPDATE revisions
        SET chapter_id_int = c.chapter_id_int
        FROM chapters c
        WHERE revisions.chapter_id = c.chapter_id
    """)

    # --- 4. drop UUID columns, rename int columns ---

    op.drop_column('revisions', 'chapter_id')
    op.drop_column('chapters', 'chapter_id')

    op.alter_column('chapters', 'chapter_id_int', new_column_name='chapter_id', nullable=False)
    op.alter_column('revisions', 'chapter_id_int', new_column_name='chapter_id', nullable=False)

    # --- 5. recreate PK, FK, and indexes ---

    op.execute("ALTER SEQUENCE chapters_chapter_id_seq_downgrade OWNED BY chapters.chapter_id")
    op.execute("ALTER TABLE chapters ALTER COLUMN chapter_id SET DEFAULT nextval('chapters_chapter_id_seq_downgrade')")

    op.create_primary_key('chapters_pkey', 'chapters', ['chapter_id'])

    op.create_foreign_key('fk_revisions_chapter_id_chapters', 'revisions', 'chapters', ['chapter_id'], ['chapter_id'])

    op.create_index(
        'ix_one_primary_revision_per_chapter', 'revisions', ['chapter_id'],
        unique=True, postgresql_where=sa.text('revision_is_primary IS TRUE')
    )
