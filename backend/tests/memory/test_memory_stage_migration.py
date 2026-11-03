"""The stage migration preserves existing runnable recording jobs."""

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateSchema, DropSchema


def test_stage_migration_round_trips_legacy_jobs_without_losing_tasks(test_engine: Engine):
    path = Path(__file__).parents[2] / "alembic/versions/d27e3f4a5b60_memory_job_stages.py"
    spec = importlib.util.spec_from_file_location("memory_stage_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    job_id, chapter_id = uuid4(), uuid4()
    with test_engine.begin() as conn:
        # An isolated schema lets the migration create tables and foreign keys
        # without touching the application's test tables. DDL rolls back on failure.
        schema = "memory_stage_migration_" + uuid4().hex
        conn.execute(CreateSchema(schema))
        conn.execute(select(func.set_config("search_path", schema, True)))
        conn.execute(text("CREATE TABLE glossaries (term_id uuid PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE memory_jobs (memory_job_id uuid PRIMARY KEY, job_params jsonb NOT NULL)"))
        conn.execute(
            text(
                "CREATE TABLE memory_chapter_tasks (memory_job_id uuid, chapter_id uuid, task_status varchar(15), attempt_count int, PRIMARY KEY(memory_job_id, chapter_id))"
            )
        )
        conn.execute(
            text(
                'INSERT INTO memory_jobs VALUES (:job, \'{"model_name":"deepseek:deepseek-v4-flash-low","toolsets":{}}\')'
            ),
            {"job": job_id},
        )
        conn.execute(
            text("INSERT INTO memory_chapter_tasks VALUES (:job, :chapter, 'failed', 3)"),
            {"job": job_id, "chapter": chapter_id},
        )
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            params = conn.scalar(text("SELECT job_params FROM memory_jobs"))
            assert params["version"] == 1
            assert conn.execute(
                text("SELECT stage_num, task_status, attempt_count FROM memory_chapter_tasks")
            ).one() == (0, "failed", 3)
            # Backfilling must not leave a silent fallback for incomplete new tasks.
            with pytest.raises(IntegrityError), conn.begin_nested():
                conn.execute(
                    text("INSERT INTO memory_chapter_tasks (memory_job_id, chapter_id) VALUES (:job, :chapter)"),
                    {"job": job_id, "chapter": uuid4()},
                )
            term_id = uuid4()
            conn.execute(text("INSERT INTO glossaries VALUES (:term)"), {"term": term_id})
            conn.execute(
                text(
                    "INSERT INTO term_translations (term_id, translation, creator_type, created_at, updated_at) VALUES (:term, 'Alpha', 'agent', now(), now())"
                ),
                {"term": term_id},
            )
            assert conn.execute(text("SELECT translation, review_status FROM term_translations")).one() == (
                "Alpha",
                "pending",
            )
            conn.execute(text("DELETE FROM glossaries WHERE term_id = :term"), {"term": term_id})
            assert conn.scalar(text("SELECT count(*) FROM term_translations")) == 0
            migration.downgrade()
        assert "version" not in conn.scalar(text("SELECT job_params FROM memory_jobs"))
        assert conn.execute(
            text("SELECT memory_job_id, chapter_id, task_status, attempt_count FROM memory_chapter_tasks")
        ).one() == (job_id, chapter_id, "failed", 3)
        conn.execute(DropSchema(schema, cascade=True))
