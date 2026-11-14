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
from src.memory.schemas import Memory as MemorySchema
from src.memory.types import Creator, MemoryType
from src.translations.actions.translate import finalize, poll, prepare, submit
from src.translations.celery_app import app
from src.translations.clients.batch_jobs import (
    BatchJobComplete,
    BatchJobFailed,
    BatchJobId,
    BatchJobPending,
    BatchJobPoll,
    BatchOutputId,
)
from src.translations.clients.registry import BATCH_CLIENT_FACTORIES
from src.translations.codecs.batch_lines import BatchItem, BatchItemResult
from src.translations.codecs.registry import MODEL_CODECS
from src.translations.jsonl import encode_translation_record, iter_translation_records
from src.translations.models import TranslationJobChapter, TranslationStage, TranslationTask
from src.translations.records import ChapterRecord, MemoriesRecord, TranslationRecord
from src.translations.schemas import TranslationJobCreate
from src.translations.tasks.jobs import create_job
from src.translations.types import TranslationDataKey
from src.translations.types import TranslationTaskStatus as State
from test_support.test_data.scenarios import DatabaseScenario
from tests.files.test_access import MemoryObjectStore

LOADED_TEXT = "Loaded chapter"


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


@pytest.fixture
def worker(testing_session_local: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch) -> MemoryObjectStore:
    store = MemoryObjectStore()
    monkeypatch.setattr("src.translations.actions.celery_actions.SessionLocal", testing_session_local)
    monkeypatch.setattr("src.translations.actions.translate.get_object_store", lambda: store)
    return store


def make_job(
    db: Session,
    scenario: DatabaseScenario,
    store: MemoryObjectStore,
    *,
    with_memories: bool = False,
    loaded: bool = True,
) -> tuple[UUID, list[TranslationRecord]]:
    """Create a translate job whose loader already wrote the returned records, unless ``loaded`` is false."""
    inputs = {}
    memories: list[MemorySchema] = []
    if with_memories:
        novel = scenario.novels["novel_1"]
        group = MemoryGroup(novel_id=novel.novel_id, memory_group_name="Context", memory_language=novel.language_code)
        db.add(group)
        db.flush()
        memory = Memory(
            memory_group_id=group.memory_group_id,
            memory_observed_in=scenario.contents["chapter_1_v2"].chapter_content_id,
            memory_type=MemoryType.FACT,
            memory_content="Use the name Alice.",
            memory_start_num=0,
            creator_type=Creator.USER,
            plugin_name="continuity",
        )
        db.add(memory)
        db.flush()
        memories = [MemorySchema.model_validate(memory)]
        inputs = {"memories": {"type": "memories", "memory_group_id": str(group.memory_group_id)}}
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
    job_id = create_job(
        db,
        TranslationJobCreate.model_validate(
            {
                "novel_id": scenario.novels["novel_1"].novel_id,
                "config": {"batch_size": 10},
                "inputs": inputs,
                "stages": [translate],
            }
        ),
    )
    loader, task = db.scalars(
        select(TranslationTask)
        .join(TranslationStage, TranslationStage.stage_id == TranslationTask.stage_id)
        .where(TranslationStage.job_id == job_id)
        .order_by(TranslationStage.stage_num)
    ).all()
    records: list[TranslationRecord] = []
    for chapter_id in db.scalars(
        select(TranslationJobChapter.chapter_id).where(TranslationJobChapter.job_id == job_id)
    ):
        records.append(ChapterRecord(chapter_id=chapter_id, stream="chapter", payload=LOADED_TEXT))
        if with_memories:
            records.append(MemoriesRecord(chapter_id=chapter_id, stream="memories", payload=memories))
    task.status = State.READY
    if loaded:
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
        loader.status, loader.output_file_id = State.COMPLETE, stored.file_id
    db.commit()
    return task.task_id, records


@pytest.mark.parametrize("with_memories", [False, True])
def test_prepare_builds_requests_from_the_previous_stage_and_persists_adapter_bytes(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    worker: MemoryObjectStore,
    with_memories: bool,
    recording_codec: RecordingCodec,
) -> None:
    task_id, records = make_job(test_db, sample_scenario, worker, with_memories=with_memories)
    chapter_ids = {record.chapter_id for record in records}

    prepare(task_id)

    test_db.expire_all()
    task = test_db.get(TranslationTask, task_id)
    assert task is not None and task.status == State.PREPARED and task.request_file_id is not None
    assert task.output_file_id is None and task.claim_token is None
    stored = test_db.get(StoredFile, task.request_file_id)
    assert stored is not None
    assert worker.objects[stored.object_key] == b'{"encoded_by_adapter":true}\n' * len(chapter_ids)
    assert {item.key for item in recording_codec.items} == {
        TranslationDataKey(chapter_id, "chapter") for chapter_id in chapter_ids
    }
    for item in recording_codec.items:
        system, user = item.request.messages
        assert item.request.model == "qwen-plus"
        assert "French" in system.content and "Preserve formal speech." in system.content
        assert ("context memories" in system.content) == with_memories
        if with_memories:
            assert user.content.endswith(LOADED_TEXT)
            assert "Use the name Alice." in user.content and '"index":0' in user.content
        else:
            assert user.content == LOADED_TEXT
        assert item.request.temperature == 0.4 and item.request.max_output_tokens == 2048
    assert worker.fetched_keys


def test_prepare_upload_failure_does_not_publish_input(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    worker: MemoryObjectStore,
    recording_codec: RecordingCodec,
) -> None:
    task_id, _ = make_job(test_db, sample_scenario, worker)
    worker.upload_error = ConnectionError("upload failed")
    with pytest.raises(ConnectionError, match="upload failed"):
        prepare(task_id)
    test_db.expire_all()
    task = test_db.get(TranslationTask, task_id)
    assert task is not None and task.request_file_id is None and task.failed_at is not None
    assert task.status == State.PREPARING
    # Only the loader's file exists.
    assert test_db.scalar(select(func.count()).select_from(StoredFile)) == 1


def test_prepare_rejects_incomplete_previous_task(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    worker: MemoryObjectStore,
    recording_codec: RecordingCodec,
) -> None:
    task_id, _ = make_job(test_db, sample_scenario, worker, loaded=False)
    with pytest.raises(ValueError, match="completed output artifact"):
        prepare(task_id)
    assert not recording_codec.items and not worker.objects


@pytest.mark.parametrize("with_memories", [False, True])
@pytest.mark.parametrize("failed", [False, True])
def test_submission_and_polling_persist_progress_before_dispatch(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    worker: MemoryObjectStore,
    recording_codec: RecordingCodec,
    queued_tasks: dict[str, Mock],
    failed: bool,
    with_memories: bool,
) -> None:
    # Finalization/recovery rely on durable provider IDs, and pending polls must
    # release their claim so a fresh worker can perform the next check.
    task_id, records = make_job(test_db, sample_scenario, worker, with_memories=with_memories)
    requests = len({record.chapter_id for record in records})
    client = FakeBatchClient()
    monkeypatch.setitem(BATCH_CLIENT_FACTORIES, "qwen-plus", lambda: client)
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
    assert client.uploads == [b'{"encoded_by_adapter":true}\n' * requests]
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
    "failure", [None, "duplicate", "missing", "stream", "foreign", "item", "malformed", "download", "upload"]
)
def test_finalize_publishes_only_the_complete_state_after_translation(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    monkeypatch: pytest.MonkeyPatch,
    worker: MemoryObjectStore,
    failure: str | None,
    with_memories: bool,
) -> None:
    task_id, records = make_job(test_db, sample_scenario, worker, with_memories=with_memories)
    chapter_ids = sorted({record.chapter_id for record in records})
    task = test_db.get(TranslationTask, task_id)
    assert task is not None
    task.status = State.PROCESSED
    task.provider_output_id = "provider-output"
    test_db.commit()

    def line(chapter_id: UUID, stream: str = "chapter") -> bytes:
        wire: dict[str, object] = {
            "custom_id": json.dumps({"chapter_id": str(chapter_id), "stream": stream}),
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
        return json.dumps(wire, ensure_ascii=False).encode()

    lines = [line(chapter_id) for chapter_id in chapter_ids]
    if failure == "duplicate":
        lines.append(lines[0])
    elif failure == "missing":
        lines.pop()
    elif failure == "stream":
        lines[0] = line(chapter_ids[0], "memories")
    elif failure == "foreign":
        lines[0] = line(UUID(int=0))
    elif failure == "malformed":
        lines[0] = b"not json"
    output = b"\r\n".join(lines)

    class OutputClient(FakeBatchClient):
        def fetch_batch_output(self, output_id: BatchOutputId) -> Iterator[bytes]:
            assert output_id == "provider-output"
            # Split even multibyte characters, and omit the final newline.
            for offset in range(0, len(output), 3):
                yield output[offset : offset + 3]
            if failure == "download":
                raise ConnectionError("download interrupted")

    if failure == "upload":
        worker.upload_error = ConnectionError("upload interrupted")
    monkeypatch.setitem(BATCH_CLIENT_FACTORIES, "qwen-plus", OutputClient)
    if failure is None:
        finalize(task_id)
    else:
        expected_error = {
            "duplicate": "Duplicate output",
            "missing": "Missing",
            "stream": "Unexpected output stream|must hold memories records",
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
        # Only the loader's file exists.
        assert task.output_file_id is None and len(worker.objects) == 1
        assert test_db.scalar(select(func.count()).select_from(StoredFile)) == 1
        return
    assert task.status == State.COMPLETE and task.failed_at is None
    assert task.output_file_id is not None
    stored = test_db.get(StoredFile, task.output_file_id)
    assert stored is not None
    # The output is the full state: untouched streams copied forward, then the translated chapters.
    assert list(iter_translation_records([worker.objects[stored.object_key]])) == [
        *(record for record in records if isinstance(record, MemoriesRecord)),
        *(
            ChapterRecord(chapter_id=chapter_id, stream="chapter", payload="Texte traduit — français")
            for chapter_id in chapter_ids
        ),
    ]
