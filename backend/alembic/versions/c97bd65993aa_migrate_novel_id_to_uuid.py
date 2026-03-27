"""migrate novel id to uuid

Revision ID: c97bd65993aa
Revises: 249e19cd905e
Create Date: 2026-03-22 03:21:01.747368+00:00

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = 'c97bd65993aa'
down_revision = '249e19cd905e'
branch_labels = None
depends_on = None


def upgrade():
    # --- 1. drop novel_parent_id self-referential FK (being removed) ---

    op.drop_constraint('fk_novels_novel_parent_id_novels', 'novels', type_='foreignkey')
    op.drop_column('novels', 'novel_parent_id')

    # --- 2. drop FK constraints referencing novels.novel_id ---

    op.drop_constraint('fk_chapters_novel_id_novels', 'chapters', type_='foreignkey')
    op.drop_constraint('novel_contributors_novel_id_fkey', 'novel_contributors', type_='foreignkey')
    op.drop_constraint('fk_label_groups_novel_id_novels', 'label_groups', type_='foreignkey')

    # --- 3. drop unique/composite constraints that include novel_id ---

    op.drop_constraint('chapter_per_novel', 'chapters', type_='unique')
    op.drop_constraint('novel_contributors_pkey', 'novel_contributors', type_='primary')

    # --- 4. drop PK on novels ---

    op.drop_constraint('novels_pkey', 'novels', type_='primary')

    # --- 5. add new UUID columns ---

    op.add_column('novels', sa.Column('novel_uuid', sa.UUID(), nullable=True))
    op.add_column('chapters', sa.Column('novel_uuid', sa.UUID(), nullable=True))
    op.add_column('novel_contributors', sa.Column('novel_uuid', sa.UUID(), nullable=True))
    op.add_column('label_groups', sa.Column('novel_uuid', sa.UUID(), nullable=True))

    # --- 6. populate UUIDs ---

    op.execute("UPDATE novels SET novel_uuid = gen_random_uuid()")

    op.execute("""
        UPDATE chapters
        SET novel_uuid = n.novel_uuid
        FROM novels n
        WHERE chapters.novel_id = n.novel_id
    """)

    op.execute("""
        UPDATE novel_contributors
        SET novel_uuid = n.novel_uuid
        FROM novels n
        WHERE novel_contributors.novel_id = n.novel_id
    """)

    op.execute("""
        UPDATE label_groups
        SET novel_uuid = n.novel_uuid
        FROM novels n
        WHERE label_groups.novel_id = n.novel_id
    """)

    # --- 7. drop old int columns, rename new columns ---

    op.drop_column('chapters', 'novel_id')
    op.drop_column('novel_contributors', 'novel_id')
    op.drop_column('label_groups', 'novel_id')
    op.drop_column('novels', 'novel_id')

    op.alter_column('novels', 'novel_uuid', new_column_name='novel_id', nullable=False)
    op.alter_column('chapters', 'novel_uuid', new_column_name='novel_id', nullable=False)
    op.alter_column('novel_contributors', 'novel_uuid', new_column_name='novel_id', nullable=False)
    op.alter_column('label_groups', 'novel_uuid', new_column_name='novel_id', nullable=False)

    # --- 8. recreate PK, FK, and unique constraints ---

    op.create_primary_key('novels_pkey', 'novels', ['novel_id'])

    op.create_primary_key('novel_contributors_pkey', 'novel_contributors', ['novel_id', 'user_id'])

    op.create_unique_constraint('chapter_per_novel', 'chapters', ['chapter_num', 'novel_id'])

    op.create_foreign_key('fk_chapters_novel_id_novels', 'chapters', 'novels', ['novel_id'], ['novel_id'])
    op.create_foreign_key('novel_contributors_novel_id_fkey', 'novel_contributors', 'novels', ['novel_id'], ['novel_id'])
    op.create_foreign_key('fk_label_groups_novel_id_novels', 'label_groups', 'novels', ['novel_id'], ['novel_id'])


def downgrade():
    # --- 1. drop FK and constraints ---

    op.drop_constraint('fk_chapters_novel_id_novels', 'chapters', type_='foreignkey')
    op.drop_constraint('novel_contributors_novel_id_fkey', 'novel_contributors', type_='foreignkey')
    op.drop_constraint('fk_label_groups_novel_id_novels', 'label_groups', type_='foreignkey')
    op.drop_constraint('chapter_per_novel', 'chapters', type_='unique')
    op.drop_constraint('novel_contributors_pkey', 'novel_contributors', type_='primary')
    op.drop_constraint('novels_pkey', 'novels', type_='primary')

    # --- 2. add old int columns ---

    op.add_column('novels', sa.Column('novel_id_int', sa.INTEGER(), autoincrement=True, nullable=True))
    op.add_column('chapters', sa.Column('novel_id_int', sa.INTEGER(), nullable=True))
    op.add_column('novel_contributors', sa.Column('novel_id_int', sa.INTEGER(), nullable=True))
    op.add_column('label_groups', sa.Column('novel_id_int', sa.INTEGER(), nullable=True))

    # --- 3. populate with sequential IDs and copy mapping ---

    op.execute("CREATE SEQUENCE novels_novel_id_seq_downgrade")
    op.execute("UPDATE novels SET novel_id_int = nextval('novels_novel_id_seq_downgrade')")

    op.execute("""
        UPDATE chapters
        SET novel_id_int = n.novel_id_int
        FROM novels n
        WHERE chapters.novel_id = n.novel_id
    """)

    op.execute("""
        UPDATE novel_contributors
        SET novel_id_int = n.novel_id_int
        FROM novels n
        WHERE novel_contributors.novel_id = n.novel_id
    """)

    op.execute("""
        UPDATE label_groups
        SET novel_id_int = n.novel_id_int
        FROM novels n
        WHERE label_groups.novel_id = n.novel_id
    """)

    # --- 4. drop UUID columns, rename int columns ---

    op.drop_column('chapters', 'novel_id')
    op.drop_column('novel_contributors', 'novel_id')
    op.drop_column('label_groups', 'novel_id')
    op.drop_column('novels', 'novel_id')

    op.alter_column('novels', 'novel_id_int', new_column_name='novel_id', nullable=False)
    op.alter_column('chapters', 'novel_id_int', new_column_name='novel_id', nullable=False)
    op.alter_column('novel_contributors', 'novel_id_int', new_column_name='novel_id', nullable=False)
    op.alter_column('label_groups', 'novel_id_int', new_column_name='novel_id', nullable=False)

    # --- 5. recreate PK, FK, unique constraints, and self-referential FK ---

    op.execute("ALTER SEQUENCE novels_novel_id_seq_downgrade OWNED BY novels.novel_id")
    op.execute("ALTER TABLE novels ALTER COLUMN novel_id SET DEFAULT nextval('novels_novel_id_seq_downgrade')")

    op.create_primary_key('novels_pkey', 'novels', ['novel_id'])
    op.create_primary_key('novel_contributors_pkey', 'novel_contributors', ['novel_id', 'user_id'])
    op.create_unique_constraint('chapter_per_novel', 'chapters', ['chapter_num', 'novel_id'])

    op.create_foreign_key('fk_chapters_novel_id_novels', 'chapters', 'novels', ['novel_id'], ['novel_id'])
    op.create_foreign_key('novel_contributors_novel_id_fkey', 'novel_contributors', 'novels', ['novel_id'], ['novel_id'])
    op.create_foreign_key('fk_label_groups_novel_id_novels', 'label_groups', 'novels', ['novel_id'], ['novel_id'])

    # restore novel_parent_id
    op.add_column('novels', sa.Column('novel_parent_id', sa.INTEGER(), nullable=True))
    op.create_foreign_key('fk_novels_novel_parent_id_novels', 'novels', 'novels', ['novel_parent_id'], ['novel_id'])
