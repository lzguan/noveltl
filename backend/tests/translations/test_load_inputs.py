from unittest.mock import Mock
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.files.models import StoredFile
from src.memory.models import Memory, MemoryGroup
from src.memory.types import Creator, MemoryType
from src.translations.actions.load_inputs import load
from src.translations.celery_app import app
from src.translations.jsonl import iter_translation_records
from src.translations.models import TranslationJobChapter, TranslationStage, TranslationTask
from src.translations.records import ChapterRecord, MemoriesRecord, TranslationRecord
from src.translations.schemas import TranslationJobCreate
from src.translations.tasks.jobs import create_job
from src.translations.types import TranslationTaskStatus as State
from test_support.test_data.scenarios import DatabaseScenario
from tests.files.test_access import MemoryObjectStore


def _group(db: Session, scenario: DatabaseScenario) -> MemoryGroup:
    novel = scenario.novels["novel_1"]
    group = MemoryGroup(novel_id=novel.novel_id, memory_group_name="Inputs", memory_language=novel.language_code)
    db.add(group)
    db.flush()
    db.add(
        Memory(
            memory_group_id=group.memory_group_id,
            memory_observed_in=scenario.contents["chapter_1_v2"].chapter_content_id,
            memory_type=MemoryType.FACT,
            memory_content="Original candidate",
            memory_start_num=0,
            creator_type=Creator.USER,
            plugin_name="continuity",
        )
    )
    db.flush()
    return group


def _request(scenario: DatabaseScenario, stage: dict, inputs: dict | None = None) -> TranslationJobCreate:
    return TranslationJobCreate.model_validate(
        {
            "novel_id": scenario.novels["novel_1"].novel_id,
            "config": {"batch_size": 100, "inputs": inputs or {}},
            "stages": [stage],
        }
    )


def _run_loader(
    db: Session,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    request: TranslationJobCreate,
    next_step: str,
) -> tuple[list[TranslationRecord], list[UUID], TranslationTask, Mock]:
    job_id = create_job(db, request)
    rows = db.execute(
        select(TranslationTask, TranslationStage.action)
        .join(TranslationStage, TranslationStage.stage_id == TranslationTask.stage_id)
        .where(TranslationStage.job_id == job_id)
        .order_by(TranslationStage.stage_num)
    ).all()
    (loader, loader_action), (following, _) = rows
    assert loader_action == "load_inputs"
    assert (loader.status, following.status) == (State.READY, State.WAITING)
    chapter_ids = list(
        db.scalars(select(TranslationJobChapter.chapter_id).where(TranslationJobChapter.job_id == job_id))
    )
    store, dispatch = MemoryObjectStore(), Mock()
    monkeypatch.setattr("src.translations.actions.celery_actions.SessionLocal", session_factory)
    monkeypatch.setattr("src.translations.actions.load_inputs.get_object_store", lambda: store)
    monkeypatch.setattr(app.tasks[next_step], "apply_async", dispatch)

    load(loader.task_id)

    db.expire_all()
    assert loader.status == State.COMPLETE and loader.output_file_id is not None
    stored = db.get(StoredFile, loader.output_file_id)
    assert stored is not None
    return list(iter_translation_records([store.objects[stored.object_key]])), chapter_ids, following, dispatch


def test_loader_captures_every_enabled_stream_and_readies_the_next_stage(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    group = _group(test_db, sample_scenario)
    inputs = {
        "memories": {
            "type": "memories",
            "memory_group_id": str(group.memory_group_id),
            "exclude_current_chapter": False,
        }
    }
    request = _request(sample_scenario, {"action": "prune_memories", "config": {"model": "qwen-plus"}}, inputs)

    records, chapter_ids, following, dispatch = _run_loader(
        test_db, testing_session_local, monkeypatch, request, "src.translations.actions.prune_memories.prepare"
    )

    assert {(record.chapter_id, record.stream, record.data_name) for record in records} == {
        (chapter_id, name, name) for chapter_id in chapter_ids for name in ("chapter", "memories")
    }
    assert any(
        isinstance(record, MemoriesRecord)
        and [item.memory_content for item in record.payload] == ["Original candidate"]
        for record in records
    )
    assert following.status == State.READY
    dispatch.assert_called_once_with((following.task_id,))


def test_loader_captures_only_chapters_when_no_streams_are_enabled(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(sample_scenario, {"action": "translate", "config": {"model": "qwen-plus"}})

    records, chapter_ids, _, _ = _run_loader(
        test_db, testing_session_local, monkeypatch, request, "src.translations.actions.translate.prepare"
    )

    assert all(isinstance(record, ChapterRecord) and record.payload for record in records)
    assert {record.chapter_id for record in records} == set(chapter_ids)


def test_creation_rejects_stages_whose_streams_the_job_does_not_load(sample_scenario: DatabaseScenario) -> None:
    with pytest.raises(ValidationError, match="stage 1 requires memories"):
        _request(sample_scenario, {"action": "prune_memories", "config": {"model": "qwen-plus"}})
    with pytest.raises(ValidationError, match="must be named 'memories'"):
        _request(
            sample_scenario,
            {"action": "translate", "config": {"model": "qwen-plus"}},
            {"side": {"type": "memories", "memory_group_id": "00000000-0000-0000-0000-000000000001"}},
        )
