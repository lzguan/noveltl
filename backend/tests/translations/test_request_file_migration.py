import importlib.util
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Engine, func, select, text
from sqlalchemy.schema import CreateSchema


def _columns(conn, table: str) -> set[str]:
    return set(
        conn.scalars(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = :table"
            ),
            {"table": table},
        )
    )


def test_migration_round_trips_and_keeps_each_tasks_request_file(test_engine: Engine) -> None:
    path = Path(__file__).parents[2] / "alembic/versions/a9d3e7c1b2f4_rename_translation_request_file.py"
    spec = importlib.util.spec_from_file_location("request_file_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    file_id, task_id = uuid4(), uuid4()
    conn = test_engine.connect()
    transaction = conn.begin()
    try:
        # An isolated schema keeps the DDL away from the application's test tables; it is rolled back.
        schema = "request_file_migration_" + uuid4().hex
        conn.execute(CreateSchema(schema))
        conn.execute(select(func.set_config("search_path", schema, True)))
        conn.execute(text("CREATE TABLE stored_files (file_id uuid PRIMARY KEY)"))
        conn.execute(
            text(
                "CREATE TABLE translation_batches (batch_id uuid PRIMARY KEY, "
                "initial_file_id uuid REFERENCES stored_files (file_id))"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE translation_tasks (task_id uuid PRIMARY KEY, "
                "input_file_id uuid REFERENCES stored_files (file_id))"
            )
        )
        conn.execute(text("INSERT INTO stored_files VALUES (:file)"), {"file": file_id})
        conn.execute(
            text("INSERT INTO translation_batches VALUES (:batch, :file)"), {"batch": uuid4(), "file": file_id}
        )
        conn.execute(text("INSERT INTO translation_tasks VALUES (:task, :file)"), {"task": task_id, "file": file_id})

        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            assert _columns(conn, "translation_batches") == {"batch_id"}
            assert _columns(conn, "translation_tasks") == {"task_id", "request_file_id"}
            assert conn.execute(text("SELECT task_id, request_file_id FROM translation_tasks")).one() == (
                task_id,
                file_id,
            )

            migration.downgrade()
            assert _columns(conn, "translation_batches") == {"batch_id", "initial_file_id"}
            assert conn.scalar(text("SELECT input_file_id FROM translation_tasks")) == file_id
            # The snapshot reference is gone for good; the restored column starts empty.
            assert conn.scalar(text("SELECT initial_file_id FROM translation_batches")) is None
    finally:
        transaction.rollback()
        conn.close()
