import json
from collections.abc import Iterable, Iterator
from datetime import timedelta
from io import BytesIO
from unittest.mock import Mock
from uuid import UUID

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from src.files.access import create_file
from src.files.models import StoredFile
from src.memory.models import Memory, MemoryGroup
from src.memory.types import Creator, MemoryType
from src.novels.models import ChapterContent
from src.translations.actions.translate import finalize, poll, prepare, submit
from src.translations.batch_jobs import (
    BatchJobComplete,
    BatchJobFailed,
    BatchJobId,
    BatchJobPending,
    BatchJobPoll,
    BatchOutputId,
)
from src.translations.batch_lines import BatchItem, BatchItemResult
from src.translations.celery_app import app
from src.translations.codecs.registry import MODEL_CODECS
from src.translations.dependencies import BATCH_CLIENT_FACTORIES
from src.translations.jsonl import encode_translation_record, iter_translation_records
from src.translations.models import TranslationStage, TranslationTask
from src.translations.records import ChapterRecord, MemoriesRecord
from src.translations.schemas import TranslationJobCreate
from src.translations.tasks.jobs import create_job
from src.translations.types import TranslationDataKey
from src.translations.types import TranslationTaskStatus as State
from test_support.test_data.scenarios import DatabaseScenario
from tests.files.test_access import MemoryObjectStore


class RecordingCodec:
    """Observe neutral requests and emit opaque bytes; no vendor is involved."""

    def __init__(self) -> None:
        self.items: list[BatchItem[TranslationDataKey]] = []

    def encode_request(self, item: BatchItem[TranslationDataKey]) -> bytes:
        self.items.append(item)
        return b'{"encoded_by_adapter":true}\n'

    def decode_result(self, line: bytes) -> BatchItemResult[TranslationDataKey]:
        raise AssertionError("Preparation must not decode provider results")


@pytest.fixture(autouse=True)
def queued_tasks(monkeypatch: pytest.MonkeyPatch) -> dict[str, Mock]:
    # Observe dispatch without running background workers or waiting for countdowns.
    queued = {name: Mock() for name in ("submit", "poll", "finalize")}
    for name, dispatch in queued.items():
        monkeypatch.setattr(app.tasks[f"src.translations.actions.translate.{name}"], "apply_async", dispatch)
    return queued


class FakeBatchClient:
    def __init__(self) -> None:
        self.uploads: list[bytes] = []
        self.polled: list[BatchJobId] = []
        self.result: BatchJobPoll = BatchJobPending()

    def create_batch_job(self, content: Iterable[bytes]) -> BatchJobId:
        self.uploads.append(b"".join(content))
        return BatchJobId("provider-job")

    def poll_batch_job(self, job_id: BatchJobId) -> BatchJobPoll:
        self.polled.append(job_id)
        return self.result

    def fetch_batch_output(self, output_id: BatchOutputId) -> Iterator[bytes]:
        raise AssertionError("Polling must not download results")


@pytest.fixture
def recording_codec(monkeypatch: pytest.MonkeyPatch) -> RecordingCodec:
    codec = RecordingCodec()
    monkeypatch.setitem(MODEL_CODECS, "qwen-plus", lambda: codec)
    return codec


def make_job(db: Session, scenario: DatabaseScenario, *, later: bool, with_memories: bool = False) -> list[UUID]:
    translate = {
        "action": "translate",
        "config": {
            "model": "qwen-plus",
            "target_language": "French",
            "instructions": "Preserve formal speech.",
            "temperature": 0.4,
            "max_output_tokens": 2048,
        },
    }
    if with_memories:
        novel = scenario.novels["novel_1"]
        group = MemoryGroup(novel_id=novel.novel_id, memory_group_name="Context", memory_language=novel.language_code)
        db.add(group)
        db.flush()
        db.add(
            Memory(
                memory_group_id=group.memory_group_id,
                memory_observed_in=scenario.contents["chapter_1_v2"].chapter_content_id,
                memory_type=MemoryType.FACT,
                memory_content="Use the name Alice.",
                memory_start_num=0,
                creator_type=Creator.USER,
                plugin_name="continuity",
            )
        )
        translate["action"] = "translate_with_memories"
        translate["config"]["memory_group_id"] = str(group.memory_group_id)
    request = TranslationJobCreate.model_validate(
        {
            "novel_id": scenario.novels["novel_1"].novel_id,
            "config": {"batch_size": 10},
            "stages": [{"action": "combine_chapter"}, translate] if later else [translate],
        }
    )
    job_id = create_job(db, request)
    return list(
        db.scalars(
            select(TranslationTask.task_id)
            .join(TranslationStage, TranslationStage.stage_id == TranslationTask.stage_id)
            .where(TranslationStage.job_id == job_id)
            .order_by(TranslationStage.stage_num)
        )
    )


@pytest.mark.parametrize("with_memories", [False, True])
@pytest.mark.parametrize("later", [False, True])
def test_prepare_uses_correct_input_and_persists_adapter_bytes(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    later: bool,
    with_memories: bool,
    recording_codec: RecordingCodec,
) -> None:
    task_ids = make_job(test_db, sample_scenario, later=later, with_memories=with_memories)
    chapter_id = sample_scenario.chapters["chapter_1"].chapter_id
    store, codec = MemoryObjectStore(), recording_codec
    expected_text = (
        "Previously produced chapter" if later else sample_scenario.contents["chapter_1_v2"].chapter_content_text
    )
    # A later source revision must not change the job's pinned input.
    test_db.add(ChapterContent(chapter_id=chapter_id, chapter_content_version=3, chapter_content_text="Too new"))
    if later:
        previous_file = create_file(
            test_db,
            store,
            BytesIO(
                encode_translation_record(MemoriesRecord(chapter_id=chapter_id, payload=[]))
                + encode_translation_record(ChapterRecord(chapter_id=chapter_id, payload=expected_text))
            ),
            storage_name="test",
            bucket="test",
            namespace="translations",
            content_type="application/jsonl",
        )
        test_db.flush([previous_file])
        previous = test_db.get(TranslationTask, task_ids[0])
        current = test_db.get(TranslationTask, task_ids[1])
        assert previous is not None and current is not None
        previous.output_file_id, previous.status = previous_file.file_id, State.COMPLETE
        current.status = State.READY
    test_db.commit()

    monkeypatch.setattr("src.translations.actions.celery_actions.SessionLocal", testing_session_local)
    monkeypatch.setattr("src.translations.actions.translate.get_object_store", lambda: store)
    prepare(task_ids[-1])
    test_db.expire_all()
    task = test_db.get(TranslationTask, task_ids[-1])
    assert task is not None and task.status == State.PREPARED and task.input_file_id is not None
    assert task.output_file_id is None and task.claim_token is None
    stored = test_db.get(StoredFile, task.input_file_id)
    assert stored is not None
    assert store.objects[stored.object_key] == b'{"encoded_by_adapter":true}\n'
    assert len(codec.items) == 1
    item = codec.items[0]
    assert item.key == TranslationDataKey(chapter_id, "chapter")
    assert item.request.model == "qwen-plus"
    if with_memories:
        assert item.request.messages[1].content.endswith(expected_text)
        if later:
            assert "Context memories:\n[]" in item.request.messages[1].content
            assert "Alice" not in item.request.messages[1].content
        else:
            assert "Use the name Alice." in item.request.messages[1].content
            assert '"index":0' in item.request.messages[1].content
    else:
        assert item.request.messages[1].content == expected_text
    assert "French" in item.request.messages[0].content
    assert "Preserve formal speech." in item.request.messages[0].content
    assert item.request.temperature == 0.4 and item.request.max_output_tokens == 2048
    assert bool(store.fetched_keys) == later


def test_prepare_upload_failure_does_not_publish_input(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    recording_codec: RecordingCodec,
) -> None:
    task_id = make_job(test_db, sample_scenario, later=False)[0]
    store = MemoryObjectStore(upload_error=ConnectionError("upload failed"))
    monkeypatch.setattr("src.translations.actions.celery_actions.SessionLocal", testing_session_local)
    monkeypatch.setattr("src.translations.actions.translate.get_object_store", lambda: store)
    with pytest.raises(ConnectionError, match="upload failed"):
        prepare(task_id)
    test_db.expire_all()
    task = test_db.get(TranslationTask, task_id)
    assert task is not None and task.input_file_id is None and task.failed_at is not None
    assert task.status == State.PREPARING
    assert test_db.scalar(select(func.count()).select_from(StoredFile)) == 0


def test_prepare_rejects_incomplete_previous_task(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    recording_codec: RecordingCodec,
) -> None:
    task_id = make_job(test_db, sample_scenario, later=True)[-1]
    task = test_db.get(TranslationTask, task_id)
    assert task is not None
    task.status = State.READY
    test_db.commit()
    store, codec = MemoryObjectStore(), recording_codec
    monkeypatch.setattr("src.translations.actions.celery_actions.SessionLocal", testing_session_local)
    monkeypatch.setattr("src.translations.actions.translate.get_object_store", lambda: store)
    with pytest.raises(ValueError, match="completed output artifact"):
        prepare(task_id)
    assert not codec.items and not store.objects


def test_memory_translation_rejects_foreign_group(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    recording_codec: RecordingCodec,
) -> None:
    task_id = make_job(test_db, sample_scenario, later=False, with_memories=True)[0]
    task = test_db.get(TranslationTask, task_id)
    assert task is not None
    stage = test_db.get(TranslationStage, task.stage_id)
    assert stage is not None
    group = test_db.get(MemoryGroup, UUID(stage.config["memory_group_id"]))
    assert group is not None
    group.novel_id = sample_scenario.novels["novel_2"].novel_id
    test_db.commit()
    store = MemoryObjectStore()
    monkeypatch.setattr("src.translations.actions.celery_actions.SessionLocal", testing_session_local)
    monkeypatch.setattr("src.translations.actions.translate.get_object_store", lambda: store)
    with pytest.raises(ValueError, match="does not belong"):
        prepare(task_id)
    test_db.expire_all()
    assert task.input_file_id is None and task.failed_at is not None
    assert not store.objects and not recording_codec.items


def test_memory_translation_requires_group_only_for_first_stage() -> None:
    stage = {"action": "translate_with_memories", "config": {"model": "qwen-plus"}}
    with pytest.raises(ValueError, match="requires memory_group_id"):
        TranslationJobCreate.model_validate({"novel_id": UUID(int=1), "config": {"batch_size": 10}, "stages": [stage]})
    request = TranslationJobCreate.model_validate(
        {
            "novel_id": UUID(int=1),
            "config": {"batch_size": 10},
            "stages": [{"action": "combine_chapter"}, stage],
        }
    )
    assert len(request.stages) == 2


@pytest.mark.parametrize("with_memories", [False, True])
@pytest.mark.parametrize("failed", [False, True])
def test_submission_and_polling_persist_progress_before_dispatch(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    recording_codec: RecordingCodec,
    queued_tasks: dict[str, Mock],
    failed: bool,
    with_memories: bool,
) -> None:
    # Finalization/recovery rely on durable provider IDs, and pending polls must
    # release their claim so a fresh worker can perform the next check.
    task_id = make_job(test_db, sample_scenario, later=False, with_memories=with_memories)[0]
    client, store = FakeBatchClient(), MemoryObjectStore()
    monkeypatch.setitem(BATCH_CLIENT_FACTORIES, "qwen-plus", lambda: client)
    monkeypatch.setattr("src.translations.actions.celery_actions.SessionLocal", testing_session_local)
    monkeypatch.setattr("src.translations.actions.translate.get_object_store", lambda: store)
    prepare(task_id)
    queued_tasks["submit"].assert_called_once_with((task_id,))

    def observe_poll_dispatch(*args: object, **kwargs: object) -> None:
        with testing_session_local() as db:
            task = db.get(TranslationTask, task_id)
            assert task is not None and task.status == State.PROCESSING
            assert task.provider_batch_id == "provider-job"
            assert task.claim_token is None and task.claim_expires_at is None
            assert task.failed_at is None

    queued_tasks["poll"].side_effect = observe_poll_dispatch
    submit(task_id)
    submit(task_id)  # Duplicate delivery must not submit twice.
    assert client.uploads == [b'{"encoded_by_adapter":true}\n']
    queued_tasks["poll"].assert_called_once_with((task_id,))
    queued_tasks["poll"].reset_mock()
    poll(task_id)
    queued_tasks["poll"].assert_called_once_with((task_id,), countdown=60)
    queued_tasks["poll"].reset_mock()

    # Early duplicate messages must neither call the provider nor reschedule.
    poll(task_id)
    queued_tasks["poll"].assert_not_called()
    assert client.polled == ["provider-job"]
    test_db.execute(
        update(TranslationTask)
        .where(TranslationTask.task_id == task_id)
        .values(next_poll_at=func.clock_timestamp() - timedelta(seconds=1))
    )
    test_db.commit()

    if failed:
        client.result = BatchJobFailed("provider rejected batch")
        with pytest.raises(RuntimeError, match="provider rejected batch"):
            poll(task_id)
    else:
        client.result = BatchJobComplete(BatchOutputId("provider-output"))
        poll(task_id)
    test_db.expire_all()
    task = test_db.get(TranslationTask, task_id)
    assert task is not None
    assert task.status == (State.PROCESSING if failed else State.PROCESSED)
    assert task.provider_output_id == (None if failed else "provider-output")
    assert (task.failed_at is not None) == failed
    assert task.claim_token is None and task.claim_expires_at is None
    assert task.output_file_id is None
    if not failed:
        assert task.next_poll_at is None
    assert client.polled == ["provider-job", "provider-job"]
    queued_tasks["poll"].assert_not_called()
    if failed:
        queued_tasks["finalize"].assert_not_called()
    else:
        queued_tasks["finalize"].assert_called_once_with((task_id,))


@pytest.mark.parametrize("with_memories", [False, True])
@pytest.mark.parametrize(
    "failure", [None, "duplicate", "missing", "component", "foreign", "item", "malformed", "download", "upload"]
)
def test_finalize_publishes_only_complete_normalized_output(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    failure: str | None,
    with_memories: bool,
) -> None:
    task_id = make_job(test_db, sample_scenario, later=False, with_memories=with_memories)[0]
    chapter_id = sample_scenario.chapters["chapter_1"].chapter_id
    task = test_db.get(TranslationTask, task_id)
    assert task is not None
    task.status = State.PROCESSED
    task.provider_output_id = "provider-output"
    test_db.commit()
    wire: dict[str, object] = {
        "custom_id": json.dumps(
            {
                "chapter_id": str(UUID(int=0) if failure == "foreign" else chapter_id),
                "data_name": "memories" if failure == "component" else "chapter",
            }
        ),
        "response": {
            "status_code": 200,
            "body": {
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Texte traduit — français"},
                        "finish_reason": "stop",
                    },
                ]
            },
        },
    }
    if failure == "item":
        wire["error"] = {"code": "failed", "message": "inference failed"}
    line = json.dumps(wire, ensure_ascii=False).encode()
    output = line
    if failure == "duplicate":
        output = line + b"\r\n" + line
    elif failure == "missing":
        output = b""
    elif failure == "malformed":
        output = b"not json"

    class OutputClient(FakeBatchClient):
        def fetch_batch_output(self, output_id: BatchOutputId) -> Iterator[bytes]:
            assert output_id == "provider-output"
            # Split even multibyte characters, and omit the final newline.
            for offset in range(0, len(output), 3):
                yield output[offset : offset + 3]
            if failure == "download":
                raise ConnectionError("download interrupted")

    store = MemoryObjectStore(upload_error=ConnectionError("upload interrupted") if failure == "upload" else None)
    monkeypatch.setitem(BATCH_CLIENT_FACTORIES, "qwen-plus", OutputClient)
    monkeypatch.setattr("src.translations.actions.celery_actions.SessionLocal", testing_session_local)
    monkeypatch.setattr("src.translations.actions.translate.get_object_store", lambda: store)
    if failure is None:
        finalize(task_id)
    else:
        expected_error = {
            "duplicate": "Duplicate output",
            "missing": "Missing",
            "component": "chapter keys",
            "foreign": "Unexpected chapter",
            "item": "inference failed",
            "malformed": "Invalid JSON",
            "download": "download interrupted",
            "upload": "upload interrupted",
        }[failure]
        with pytest.raises((ValueError, ConnectionError), match=expected_error):
            finalize(task_id)
    test_db.expire_all()
    task = test_db.get(TranslationTask, task_id)
    assert task is not None
    assert task.claim_token is None and task.claim_expires_at is None
    if failure is not None:
        assert task.status == State.FINALIZING and task.failed_at is not None
        assert task.output_file_id is None and not store.objects
        assert test_db.scalar(select(func.count()).select_from(StoredFile)) == 0
    else:
        assert task.status == State.COMPLETE and task.failed_at is None
        assert task.output_file_id is not None
        stored = test_db.get(StoredFile, task.output_file_id)
        assert stored is not None
        assert list(iter_translation_records([store.objects[stored.object_key]])) == [
            ChapterRecord(chapter_id=chapter_id, payload="Texte traduit — français"),
        ]
