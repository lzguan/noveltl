import json
from collections.abc import Iterable, Iterator
from unittest.mock import Mock

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.files.models import StoredFile
from src.memory.models import Memory, MemoryGroup
from src.memory.types import Creator, MemoryType
from src.translations.actions import load_inputs, prune_memories, translate
from src.translations.celery_app import app
from src.translations.clients.batch_jobs import BatchJobComplete, BatchJobId, BatchJobPoll, BatchOutputId
from src.translations.clients.registry import BATCH_CLIENT_FACTORIES
from src.translations.jsonl import iter_translation_records
from src.translations.models import TranslationJobChapter, TranslationStage, TranslationTask
from src.translations.records import ChapterRecord, MemoriesRecord, TranslationRecord
from src.translations.schemas import TranslationJobCreate
from src.translations.tasks.jobs import create_job
from src.translations.types import TranslationTaskStatus as State
from test_support.test_data.scenarios import DatabaseScenario
from tests.files.test_access import MemoryObjectStore

CANDIDATES = ("First candidate", "Second candidate")


class EchoClient:
    def __init__(self) -> None:
        self.batches: list[list[dict]] = []

    def create_batch_job(self, content: Iterable[bytes]) -> BatchJobId:
        self.batches.append([json.loads(line) for line in b"".join(content).splitlines()])
        return BatchJobId(str(len(self.batches) - 1))

    def poll_batch_job(self, job_id: BatchJobId) -> BatchJobPoll:
        return BatchJobComplete(BatchOutputId(job_id))

    def fetch_batch_output(self, output_id: BatchOutputId) -> Iterator[bytes]:
        for request in self.batches[int(output_id)]:
            system = request["body"]["messages"][0]["content"]
            text = "[0]" if system.startswith("Select the context memories") else "Translated chapter"
            body = {
                "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}]
            }
            yield (
                json.dumps({"custom_id": request["custom_id"], "response": {"status_code": 200, "body": body}}).encode()
                + b"\n"
            )


@pytest.fixture
def pipeline(
    test_db: Session, testing_session_local: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> tuple[MemoryObjectStore, EchoClient]:
    store, client = MemoryObjectStore(), EchoClient()
    monkeypatch.setattr("src.translations.actions.celery_actions.SessionLocal", testing_session_local)
    for module in ("load_inputs", "prune_memories", "translate"):
        monkeypatch.setattr(f"src.translations.actions.{module}.get_object_store", lambda: store)
    monkeypatch.setitem(BATCH_CLIENT_FACTORIES, "qwen-plus", lambda: client)
    for name, task in app.tasks.items():
        if name.startswith("src.translations.actions."):
            monkeypatch.setattr(task, "apply_async", Mock())
    return store, client


def _tasks(db: Session, scenario: DatabaseScenario, stages: list[dict], inputs: dict) -> list[TranslationTask]:
    job_id = create_job(
        db,
        TranslationJobCreate.model_validate(
            {
                "novel_id": scenario.novels["novel_1"].novel_id,
                "config": {"batch_size": 100},
                "inputs": inputs,
                "stages": stages,
            }
        ),
    )
    assert db.scalar(select(TranslationJobChapter.chapter_id).where(TranslationJobChapter.job_id == job_id))
    return list(
        db.scalars(
            select(TranslationTask)
            .join(TranslationStage, TranslationStage.stage_id == TranslationTask.stage_id)
            .where(TranslationStage.job_id == job_id)
            .order_by(TranslationStage.stage_num)
        )
    )


def _output(db: Session, store: MemoryObjectStore, task: TranslationTask) -> list[TranslationRecord]:
    db.expire_all()
    assert task.status == State.COMPLETE and task.output_file_id is not None
    stored = db.get(StoredFile, task.output_file_id)
    assert stored is not None
    return list(iter_translation_records([store.objects[stored.object_key]]))


def test_job_loads_prunes_and_translates_with_each_stage_carrying_the_full_state(
    test_db: Session, sample_scenario: DatabaseScenario, pipeline: tuple[MemoryObjectStore, EchoClient]
) -> None:
    store, client = pipeline
    novel = sample_scenario.novels["novel_1"]
    group = MemoryGroup(novel_id=novel.novel_id, memory_group_name="Pipeline", memory_language=novel.language_code)
    test_db.add(group)
    test_db.flush()
    for content in CANDIDATES:
        test_db.add(
            Memory(
                memory_group_id=group.memory_group_id,
                memory_observed_in=sample_scenario.contents["chapter_1_v2"].chapter_content_id,
                memory_type=MemoryType.FACT,
                memory_content=content,
                memory_start_num=0,
                creator_type=Creator.USER,
                plugin_name="continuity",
            )
        )
    test_db.flush()
    inputs = {
        "memories": {
            "type": "memories",
            "memory_group_id": str(group.memory_group_id),
            "exclude_current_chapter": False,
        }
    }
    stages = [
        {"action": "prune_memories", "config": {"model": "qwen-plus"}},
        {"action": "translate", "config": {"model": "qwen-plus"}},
    ]
    loader, pruning, translation = _tasks(test_db, sample_scenario, stages, inputs)

    load_inputs.load(loader.task_id)
    for step in (prune_memories.prepare, prune_memories.submit, prune_memories.poll, prune_memories.finalize):
        step(pruning.task_id)
    for step in (translate.prepare, translate.submit, translate.poll, translate.finalize):
        step(translation.task_id)

    loaded = _output(test_db, store, loader)
    pruned = _output(test_db, store, pruning)
    translated = _output(test_db, store, translation)
    chapter_ids = {record.chapter_id for record in loaded}
    expected_keys = {(chapter_id, stream) for chapter_id in chapter_ids for stream in ("chapter", "memories")}
    # Every stage's file is the full state: its own outputs plus everything it left alone.
    for output in (loaded, pruned, translated):
        assert {(record.chapter_id, record.stream) for record in output} == expected_keys

    def chapters(records: list[TranslationRecord]) -> dict:
        return {record.chapter_id: record.payload for record in records if isinstance(record, ChapterRecord)}

    def memories(records: list[TranslationRecord]) -> dict:
        return {record.chapter_id: record.payload for record in records if isinstance(record, MemoriesRecord)}

    source_text, kept = chapters(loaded), memories(pruned)
    assert chapters(pruned) == source_text
    assert all(len(payload) <= 1 for payload in kept.values()) and any(kept.values())
    assert set(chapters(translated).values()) == {"Translated chapter"}
    assert memories(translated) == kept

    prompts = [request["body"]["messages"][1]["content"] for request in client.batches[1]]
    assert len(prompts) == len(chapter_ids)
    for prompt in prompts:
        # Pruning kept one of the two candidates, and translation saw only that one.
        assert prompt.startswith("Context memories:") and sum(name in prompt for name in CANDIDATES) <= 1
        assert any(text in prompt for text in source_text.values())
    assert any(name in prompt for prompt in prompts for name in CANDIDATES)


def test_translation_without_a_memories_stream_sends_only_the_chapter(
    test_db: Session, sample_scenario: DatabaseScenario, pipeline: tuple[MemoryObjectStore, EchoClient]
) -> None:
    store, client = pipeline
    loader, translation = _tasks(
        test_db, sample_scenario, [{"action": "translate", "config": {"model": "qwen-plus"}}], {}
    )

    load_inputs.load(loader.task_id)
    for step in (translate.prepare, translate.submit, translate.poll, translate.finalize):
        step(translation.task_id)

    source = {record.chapter_id: record.payload for record in _output(test_db, store, loader)}
    assert {request["body"]["messages"][1]["content"] for request in client.batches[0]} == set(source.values())
    assert all("context memories" not in request["body"]["messages"][0]["content"] for request in client.batches[0])
    assert {record.chapter_id for record in _output(test_db, store, translation)} == set(source)
