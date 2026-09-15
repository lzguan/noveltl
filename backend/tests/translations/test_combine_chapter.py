from io import BytesIO
from unittest.mock import Mock

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.files.access import create_file
from src.files.models import StoredFile
from src.novels.models import ChapterContent
from src.translations.actions.combine_chapter import combine
from src.translations.celery_app import app
from src.translations.jsonl import encode_translation_record, iter_translation_records
from src.translations.models import TranslationStage, TranslationTask
from src.translations.records import ChapterRecord, MemoriesRecord
from src.translations.schemas import TranslationJobCreate
from src.translations.tasks.jobs import create_job
from src.translations.types import TranslationTaskStatus as State
from test_support.test_data.scenarios import DatabaseScenario
from tests.files.test_access import MemoryObjectStore


@pytest.mark.parametrize("failure", [None, "missing", "duplicate", "incomplete", "upload"])
def test_combine_publishes_pinned_chapter_and_memories_before_advancing(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    failure: str | None,
) -> None:
    # The next action requires a complete artifact, pinned source text, and the
    # preceding memory snapshots. Only the S3 and queue boundaries are doubled.
    job_id = create_job(
        test_db,
        TranslationJobCreate.model_validate(
            {
                "novel_id": sample_scenario.novels["novel_1"].novel_id,
                "config": {"batch_size": 10},
                "stages": [
                    {"action": "prune_memories"},
                    {"action": "combine_chapter"},
                    {"action": "translate", "config": {"model": "qwen-plus"}},
                ],
            }
        ),
    )
    previous, current, following = test_db.scalars(
        select(TranslationTask)
        .join(TranslationStage, TranslationStage.stage_id == TranslationTask.stage_id)
        .where(TranslationStage.job_id == job_id)
        .order_by(TranslationStage.stage_num)
    ).all()
    current_id, following_id = current.task_id, following.task_id
    chapter_id = sample_scenario.chapters["chapter_1"].chapter_id
    memory = MemoriesRecord(chapter_id=chapter_id, payload=[])
    data = encode_translation_record(memory)
    if failure == "missing":
        data = b""
    elif failure == "duplicate":
        data += data
    store = MemoryObjectStore()
    stored = create_file(
        test_db,
        store,
        BytesIO(data),
        storage_name="test",
        bucket="test",
        namespace="translations",
        content_type="application/jsonl",
    )
    test_db.flush([stored])
    previous.output_file_id = stored.file_id
    previous.status = State.FINALIZING if failure == "incomplete" else State.COMPLETE
    current.status = State.READY
    test_db.add(
        ChapterContent(chapter_id=chapter_id, chapter_content_version=3, chapter_content_text="New unpinned revision")
    )
    test_db.commit()
    if failure == "upload":
        store.upload_error = ConnectionError("upload interrupted")
    monkeypatch.setattr("src.translations.actions.celery_actions.SessionLocal", testing_session_local)
    monkeypatch.setattr("src.translations.actions.combine_chapter.get_object_store", lambda: store)

    def observe_dispatch(*args: object, **kwargs: object) -> None:
        with testing_session_local() as db:
            task = db.get(TranslationTask, current_id)
            next_task = db.get(TranslationTask, following_id)
            assert task is not None and task.status == State.COMPLETE and task.output_file_id is not None
            assert next_task is not None and next_task.status == State.READY

    dispatch = Mock(side_effect=observe_dispatch)
    monkeypatch.setattr(app.tasks["src.translations.actions.translate.prepare"], "apply_async", dispatch)
    if failure is None:
        combine(current_id)
    else:
        message = {
            "missing": "Missing",
            "duplicate": "Duplicate",
            "incomplete": "completed output artifact",
            "upload": "upload interrupted",
        }[failure]
        with pytest.raises((ValueError, ConnectionError), match=message):
            combine(current_id)
    test_db.expire_all()
    assert current.claim_token is None
    assert current.input_file_id is None and current.provider_batch_id is None
    if failure is not None:
        assert current.status == State.FINALIZING and current.failed_at is not None
        assert current.output_file_id is None and following.status == State.WAITING
        assert len(store.objects) == 1
        dispatch.assert_not_called()
    else:
        assert current.output_file_id is not None and current.failed_at is None
        output = test_db.get(StoredFile, current.output_file_id)
        assert output is not None
        records = list(iter_translation_records([store.objects[output.object_key]]))
        assert records == [
            memory,
            ChapterRecord(chapter_id=chapter_id, payload=sample_scenario.contents["chapter_1_v2"].chapter_content_text),
        ]
        dispatch.assert_called_once_with((following_id,))
