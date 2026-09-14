from io import BytesIO
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from src.files.access import create_file
from src.files.models import StoredFile
from src.novels.models import ChapterContent
from src.translations.actions.translate import prepare
from src.translations.batch_lines import BatchItem, BatchItemResult
from src.translations.codecs.registry import MODEL_CODECS
from src.translations.jsonl import encode_translation_record
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


@pytest.fixture
def recording_codec(monkeypatch: pytest.MonkeyPatch) -> RecordingCodec:
    codec = RecordingCodec()
    monkeypatch.setitem(MODEL_CODECS, "qwen-plus", lambda: codec)
    return codec


def make_job(db: Session, scenario: DatabaseScenario, *, later: bool) -> list[UUID]:
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


@pytest.mark.parametrize("later", [False, True])
def test_prepare_uses_correct_input_and_persists_adapter_bytes(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    later: bool,
    recording_codec: RecordingCodec,
) -> None:
    task_ids = make_job(test_db, sample_scenario, later=later)
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
