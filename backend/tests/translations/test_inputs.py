from io import BytesIO
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.files.access import create_file
from src.memory.models import Memory, MemoryGroup
from src.memory.schemas import Memory as MemorySchema
from src.memory.types import Creator, MemoryType
from src.translations.actions.actions import ActionTaskContext
from src.translations.actions.common.inputs import MemoryInputs, iter_initial_records, resolve_inputs
from src.translations.jsonl import encode_translation_record
from src.translations.models import TranslationJobChapter, TranslationStage, TranslationTask
from src.translations.records import ChapterRecord, MemoriesRecord, TranslationRecord
from src.translations.schemas import TranslationJobCreate
from src.translations.tasks.jobs import create_job
from src.translations.types import DataT
from src.translations.types import TranslationTaskStatus as State
from test_support.test_data.scenarios import DatabaseScenario
from tests.files.test_access import MemoryObjectStore

BOTH: DataT = frozenset(("chapter", "memories"))


def _memory(db: Session, scenario: DatabaseScenario, novel_key: str = "novel_1") -> tuple[MemoryGroup, Memory]:
    novel = scenario.novels[novel_key]
    group = MemoryGroup(novel_id=novel.novel_id, memory_group_name="Inputs", memory_language=novel.language_code)
    db.add(group)
    db.flush()
    memory = Memory(
        memory_group_id=group.memory_group_id,
        memory_observed_in=scenario.contents["chapter_1_v2"].chapter_content_id,
        memory_type=MemoryType.FACT,
        memory_content="Original candidate",
        memory_start_num=0,
        creator_type=Creator.USER,
        plugin_name="continuity",
    )
    db.add(memory)
    db.flush()
    return group, memory


def _pruning_job(
    db: Session, scenario: DatabaseScenario, group: MemoryGroup
) -> tuple[list[TranslationTask], list[TranslationStage], list[UUID]]:
    pruning = {"action": "prune_memories", "config": {"model": "qwen-plus"}}
    first = {
        "action": "prune_memories",
        "config": {"model": "qwen-plus", "memory_group_id": str(group.memory_group_id)},
    }
    stages = [first, {"action": "combine_chapter"}, pruning, {"action": "combine_chapter"}]
    job_id = create_job(
        db,
        TranslationJobCreate.model_validate(
            {"novel_id": scenario.novels["novel_1"].novel_id, "config": {"batch_size": 100}, "stages": stages}
        ),
    )
    rows = db.execute(
        select(TranslationTask, TranslationStage)
        .join(TranslationStage, TranslationStage.stage_id == TranslationTask.stage_id)
        .where(TranslationStage.job_id == job_id)
        .order_by(TranslationStage.stage_num)
    ).all()
    assert len(rows) == len(stages)
    chapter_ids = list(
        db.scalars(select(TranslationJobChapter.chapter_id).where(TranslationJobChapter.job_id == job_id))
    )
    return [task for task, _ in rows], [stage for _, stage in rows], chapter_ids


def _context(db: Session, task: TranslationTask) -> ActionTaskContext:
    return ActionTaskContext(db=db, task=task, claim_token=uuid4(), renew_lease=Mock())


def _complete(db: Session, store: MemoryObjectStore, task: TranslationTask, records: list[TranslationRecord]) -> None:
    stored = create_file(
        db,
        store,
        BytesIO(b"".join(encode_translation_record(record) for record in records)),
        storage_name="test",
        bucket="test",
        namespace="translations",
        content_type="application/jsonl",
    )
    db.flush()
    task.status, task.output_file_id = State.COMPLETE, stored.file_id
    db.flush()


def _by_key(records: list[TranslationRecord]) -> list[TranslationRecord]:
    return sorted(records, key=lambda record: (record.data_name, record.chapter_id))


def test_each_component_comes_from_its_latest_producer(test_db: Session, sample_scenario: DatabaseScenario) -> None:
    group, memory = _memory(test_db, sample_scenario)
    tasks, stages, chapter_ids = _pruning_job(test_db, sample_scenario, group)
    store = MemoryObjectStore()
    candidate = MemorySchema.model_validate(memory)
    chapters: list[TranslationRecord] = [
        ChapterRecord(chapter_id=chapter_id, payload="Combined text") for chapter_id in chapter_ids
    ]
    unpruned: list[TranslationRecord] = [
        MemoriesRecord(chapter_id=chapter_id, payload=[candidate]) for chapter_id in chapter_ids
    ]
    pruned: list[TranslationRecord] = [MemoriesRecord(chapter_id=chapter_id, payload=[]) for chapter_id in chapter_ids]
    # Stage 1 (combine) produced both components; stage 2 (prune) then replaced memories only.
    _complete(test_db, store, tasks[1], chapters + unpruned)
    _complete(test_db, store, tasks[2], pruned)

    resolved = list(resolve_inputs(_context(test_db, tasks[3]), store, stages[3], BOTH))

    assert _by_key(resolved) == _by_key(chapters + pruned)
    assert list(resolve_inputs(_context(test_db, tasks[2]), store, stages[2], BOTH)) == chapters + unpruned


def test_producers_must_exist_and_be_complete(test_db: Session, sample_scenario: DatabaseScenario) -> None:
    group, _ = _memory(test_db, sample_scenario)
    tasks, stages, chapter_ids = _pruning_job(test_db, sample_scenario, group)
    store = MemoryObjectStore()

    with pytest.raises(ValueError, match="No earlier stage produces: chapter, memories"):
        list(resolve_inputs(_context(test_db, tasks[0]), store, stages[0], BOTH))
    with pytest.raises(ValueError, match="Stage 0 must have a completed output artifact"):
        list(resolve_inputs(_context(test_db, tasks[1]), store, stages[1], frozenset(("memories",))))

    pruned: list[TranslationRecord] = [MemoriesRecord(chapter_id=chapter_id, payload=[]) for chapter_id in chapter_ids]
    _complete(test_db, store, tasks[0], pruned)
    assert list(resolve_inputs(_context(test_db, tasks[1]), store, stages[1], frozenset(("memories",)))) == pruned
    with pytest.raises(ValueError, match="No earlier stage produces: chapter"):
        list(resolve_inputs(_context(test_db, tasks[1]), store, stages[1], BOTH))
    _complete(test_db, store, tasks[0], pruned[1:])
    with pytest.raises(ValueError, match="Missing"):
        list(resolve_inputs(_context(test_db, tasks[1]), store, stages[1], frozenset(("memories",))))


def test_initial_records_cover_every_chapter_and_reject_foreign_groups(
    test_db: Session, sample_scenario: DatabaseScenario
) -> None:
    group, _ = _memory(test_db, sample_scenario)
    foreign, _ = _memory(test_db, sample_scenario, "novel_2")
    tasks, stages, chapter_ids = _pruning_job(test_db, sample_scenario, group)
    context = _context(test_db, tasks[0])

    chapters_only = list(iter_initial_records(context, stages[0], None))
    assert {record.chapter_id for record in chapters_only} == set(chapter_ids)
    assert all(isinstance(record, ChapterRecord) for record in chapters_only)

    inputs = MemoryInputs(group.memory_group_id, exclude_current_chapter=False)
    records = list(iter_initial_records(context, stages[0], inputs))
    assert {(record.chapter_id, record.data_name) for record in records} == {
        (chapter_id, name) for chapter_id in chapter_ids for name in BOTH
    }
    assert any(
        isinstance(record, MemoriesRecord)
        and [item.memory_content for item in record.payload] == ["Original candidate"]
        for record in records
    )
    with pytest.raises(ValueError, match="does not belong"):
        list(iter_initial_records(context, stages[0], MemoryInputs(foreign.memory_group_id)))
