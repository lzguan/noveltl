import importlib.util
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Connection, Engine, delete, func, insert, inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateSchema, DropSchema

from src.memory.models import Memory
from src.memory.plugins.conventions.models import TranslationConvention
from src.memory.plugins.glossary.models import GlossaryAssociation, GlossaryTerm
from src.memory.plugins.translations.models import TermTranslation
from src.memory.shadow_models import (
    MemoryWorkspace,
    ShadowConvention,
    ShadowGlossaryAssociation,
    ShadowMemory,
    ShadowTerm,
    ShadowTermTranslation,
)
from src.memory.types import Creator, MemoryType
from src.models import Base

SHADOW_MODELS = (ShadowMemory, ShadowTerm, ShadowGlossaryAssociation, ShadowTermTranslation, ShadowConvention)
NEW_TABLES = {MemoryWorkspace.__tablename__, *(model.__tablename__ for model in SHADOW_MODELS)}
type ShadowModel = ShadowMemory | ShadowTerm | ShadowGlossaryAssociation | ShadowTermTranslation | ShadowConvention


@dataclass
class ShadowSchema:
    connection: Connection
    migration: ModuleType
    job_id: UUID
    chapter_id: UUID
    group_id: UUID
    content_id: UUID
    schema_name: str


@pytest.fixture
def shadow_schema(test_engine: Engine) -> Iterator[ShadowSchema]:
    path = Path(__file__).parents[2] / "alembic/versions/f8b2c4d6e901_add_memory_shadow_tables.py"
    spec = importlib.util.spec_from_file_location("memory_shadow_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with test_engine.begin() as connection:
        schema = "memory_shadow_test_" + uuid4().hex
        connection.execute(CreateSchema(schema))
        connection.execute(select(func.set_config("search_path", schema + ",public", True)))
        # Published memory/term tables intentionally do not exist in this schema:
        # staged identities must be usable before publishing their parents.
        connection.execute(text("CREATE TABLE memory_groups (memory_group_id uuid PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE chapter_contents (chapter_content_id uuid PRIMARY KEY)"))
        connection.execute(
            text(
                "CREATE TABLE memory_chapter_tasks (memory_job_id uuid, chapter_id uuid, stage_num int, "
                "PRIMARY KEY (memory_job_id, chapter_id, stage_num))"
            )
        )
        data = ShadowSchema(connection, migration, uuid4(), uuid4(), uuid4(), uuid4(), schema)
        connection.execute(text("INSERT INTO memory_groups VALUES (:id)"), {"id": data.group_id})
        connection.execute(text("INSERT INTO chapter_contents VALUES (:id)"), {"id": data.content_id})
        connection.execute(
            text("INSERT INTO memory_chapter_tasks VALUES (:job, :chapter, 0)"),
            {
                "job": data.job_id,
                "chapter": data.chapter_id,
            },
        )
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            yield data
        connection.execute(DropSchema(schema, cascade=True))


def _workspace(data: ShadowSchema) -> UUID:
    workspace_id = uuid4()
    data.connection.execute(
        insert(MemoryWorkspace).values(
            workspace_id=workspace_id,
            memory_job_id=data.job_id,
            chapter_id=data.chapter_id,
            stage_num=0,
        )
    )
    return workspace_id


def _payloads(data: ShadowSchema) -> list[tuple[type[ShadowModel], dict[str, Any]]]:
    memory_id, term_id = uuid4(), uuid4()
    return [
        (
            ShadowMemory,
            {
                "memory_id": memory_id,
                "memory_group_id": data.group_id,
                "memory_type": MemoryType.FACT,
                "memory_observed_in": data.content_id,
                "memory_start_num": 1,
                "memory_content": "Example fact.",
                "creator_type": Creator.AGENT,
                "plugin_name": "glossary",
            },
        ),
        (ShadowTerm, {"term_id": term_id, "memory_group_id": data.group_id, "term": "Example"}),
        (ShadowGlossaryAssociation, {"term_id": term_id, "memory_id": memory_id}),
        (ShadowTermTranslation, {"term_id": term_id, "translation": "Example", "creator_type": Creator.AGENT}),
        (
            ShadowConvention,
            {
                "convention_id": uuid4(),
                "memory_group_id": data.group_id,
                "category": "naming",
                "title": "Example policy",
                "rule": "Preserve source name forms.",
                "creator_type": Creator.AGENT,
            },
        ),
    ]


def test_shadow_payload_columns_preserve_published_row_types():
    for published, shadow in [
        (Memory, ShadowMemory),
        (GlossaryTerm, ShadowTerm),
        (GlossaryAssociation, ShadowGlossaryAssociation),
        (TermTranslation, ShadowTermTranslation),
        (TranslationConvention, ShadowConvention),
    ]:
        for column in published.__table__.columns:
            staged = shadow.__table__.columns[column.name]
            assert str(column.type) == str(staged.type)
            assert column.nullable == staged.nullable
            assert getattr(column.type, "enums", None) == getattr(staged.type, "enums", None)


def test_migration_matches_registered_shadow_models(shadow_schema: ShadowSchema):
    def include_object(obj, _name, kind, _reflected, _compare_to):
        return obj.name in NEW_TABLES if kind == "table" else obj.table.name in NEW_TABLES

    context = MigrationContext.configure(
        shadow_schema.connection,
        opts={
            "include_object": include_object,
            "compare_server_default": True,
        },
    )
    assert compare_metadata(context, Base.metadata) == []


def test_drafts_with_unpublished_ids_are_isolated_and_cascade_with_their_workspace(shadow_schema: ShadowSchema):
    data = shadow_schema
    first, second = _workspace(data), _workspace(data)
    for model, payload in _payloads(data):
        for workspace_id in (first, second):
            data.connection.execute(insert(model).values(workspace_id=workspace_id, **payload))
        assert data.connection.scalar(select(func.count()).select_from(model)) == 2
    data.connection.execute(delete(MemoryWorkspace).where(MemoryWorkspace.workspace_id == first))
    for model in SHADOW_MODELS:
        assert data.connection.scalar(select(model.workspace_id)) == second
        assert data.connection.scalar(select(model.deleted)) is False
    data.connection.execute(text("DELETE FROM memory_chapter_tasks"))
    assert data.connection.scalar(select(func.count()).select_from(MemoryWorkspace)) == 0
    for model in SHADOW_MODELS:
        assert data.connection.scalar(select(func.count()).select_from(model)) == 0


def test_workspaces_require_a_real_task(shadow_schema: ShadowSchema):
    data = shadow_schema
    with pytest.raises(IntegrityError), data.connection.begin_nested():
        data.connection.execute(
            insert(MemoryWorkspace).values(
                memory_job_id=data.job_id,
                chapter_id=uuid4(),
                stage_num=0,
            )
        )


@pytest.mark.parametrize("payload_index", range(5))
def test_tombstones_can_stage_deletions(shadow_schema: ShadowSchema, payload_index: int):
    data = shadow_schema
    workspace_id = _workspace(data)
    model, payload = _payloads(data)[payload_index]
    data.connection.execute(insert(model).values(workspace_id=workspace_id, deleted=True, **payload))
    assert data.connection.scalar(select(model.deleted)) is True


def test_active_term_names_are_unique_but_tombstones_allow_replacement(shadow_schema: ShadowSchema):
    data = shadow_schema
    workspace_id = _workspace(data)
    payload = {"workspace_id": workspace_id, "memory_group_id": data.group_id, "term": "Example"}
    original_id = uuid4()
    data.connection.execute(insert(ShadowTerm).values(term_id=original_id, **payload))
    with pytest.raises(IntegrityError), data.connection.begin_nested():
        data.connection.execute(insert(ShadowTerm).values(**payload))
    data.connection.execute(update(ShadowTerm).where(ShadowTerm.term_id == original_id).values(deleted=True))
    data.connection.execute(insert(ShadowTerm).values(**payload))
    assert data.connection.scalar(select(func.count()).select_from(ShadowTerm).where(~ShadowTerm.deleted)) == 1


@pytest.mark.parametrize("invalid", ["interval", "translation", "title", "rule", "summary"])
def test_shadow_payloads_keep_published_content_constraints(shadow_schema: ShadowSchema, invalid: str):
    data = shadow_schema
    workspace_id = _workspace(data)
    payloads = _payloads(data)
    if invalid in ("interval", "summary"):
        model, payload = payloads[0]
        if invalid == "interval":
            payload["memory_end_num"] = payload["memory_start_num"]
        else:
            payload.update(memory_type=MemoryType.SUMMARY, plugin_name="continuity")
            data.connection.execute(insert(model).values(workspace_id=workspace_id, **payload))
            payload["memory_id"] = uuid4()
    elif invalid == "translation":
        model, payload = payloads[3]
        payload["translation"] = "   "
    else:
        model, payload = payloads[4]
        payload[invalid] = "   "
    with pytest.raises(IntegrityError), data.connection.begin_nested():
        data.connection.execute(insert(model).values(workspace_id=workspace_id, **payload))


def test_downgrade_refuses_workspaces_and_preserves_parent_tables(shadow_schema: ShadowSchema):
    data = shadow_schema
    _workspace(data)
    with pytest.raises(RuntimeError, match="Discard or export"):
        data.migration.downgrade()
    assert NEW_TABLES.issubset(inspect(data.connection).get_table_names(schema=data.schema_name))
    data.connection.execute(delete(MemoryWorkspace))
    data.migration.downgrade()
    assert NEW_TABLES.isdisjoint(inspect(data.connection).get_table_names(schema=data.schema_name))
    assert data.connection.scalar(text("SELECT count(*) FROM memory_chapter_tasks")) == 1
    assert data.connection.scalar(text("SELECT count(*) FROM memory_groups")) == 1
    data.migration.upgrade()
    assert NEW_TABLES.issubset(inspect(data.connection).get_table_names(schema=data.schema_name))
