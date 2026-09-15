import json
from collections.abc import Iterable, Iterator
from io import BytesIO
from unittest.mock import Mock

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from src.files.access import create_file
from src.files.models import StoredFile
from src.memory.models import Memory, MemoryGroup
from src.memory.schemas import Memory as MemorySchema
from src.memory.types import Creator, MemoryType
from src.translations.actions.prune_memories import finalize, poll, prepare, submit
from src.translations.batch_jobs import BatchJobComplete, BatchJobId, BatchJobPoll, BatchOutputId
from src.translations.celery_app import app
from src.translations.dependencies import BATCH_CLIENT_FACTORIES
from src.translations.jsonl import encode_translation_record, iter_translation_records
from src.translations.models import TranslationBatch, TranslationStage, TranslationTask
from src.translations.records import ChapterRecord, MemoriesRecord
from src.translations.schemas import TranslationJobCreate
from src.translations.tasks.jobs import create_job
from src.translations.types import TranslationTaskStatus as State
from test_support.test_data.scenarios import DatabaseScenario
from tests.files.test_access import MemoryObjectStore


class PruningClient:
    def __init__(self, response: str) -> None:
        self.requests: list[dict] = []
        self.response = response

    def create_batch_job(self, content: Iterable[bytes]) -> BatchJobId:
        self.requests = [json.loads(line) for line in b"".join(content).splitlines()]
        return BatchJobId("pruning-job")

    def poll_batch_job(self, job_id: BatchJobId) -> BatchJobPoll:
        assert job_id == "pruning-job"
        return BatchJobComplete(BatchOutputId("pruning-output"))

    def fetch_batch_output(self, output_id: BatchOutputId) -> Iterator[bytes]:
        assert output_id == "pruning-output"
        output = b"".join(
            json.dumps(
                {
                    "custom_id": request["custom_id"],
                    "response": {
                        "status_code": 200,
                        "body": {
                            "choices": [
                                {
                                    "index": 0,
                                    "message": {"role": "assistant", "content": self.response},
                                    "finish_reason": "stop",
                                }
                            ]
                        },
                    },
                }
            ).encode()
            + b"\n"
            for request in reversed(self.requests)
        )
        for offset in range(0, len(output), 7):
            yield output[offset : offset + 7]


@pytest.mark.parametrize("later", [False, True])
@pytest.mark.parametrize("response", ["[0]", "[]", "[99]", "[true]", "prepare_upload"])
def test_pruning_resolves_saved_candidates_and_advances_only_valid_output(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    later: bool,
    response: str,
) -> None:
    # Finalization must resolve the model's indices against preparation's exact
    # snapshots, even after DB memory content changes. DB transactions are real;
    # the unavailable provider, S3, and queue dispatch are external test seams.
    novel = sample_scenario.novels["novel_1"]
    chapter = sample_scenario.chapters["chapter_1"]
    group = MemoryGroup(novel_id=novel.novel_id, memory_group_name="Pruning", memory_language=novel.language_code)
    test_db.add(group)
    test_db.flush()
    memory = Memory(
        memory_group_id=group.memory_group_id,
        memory_observed_in=sample_scenario.contents["chapter_1_v2"].chapter_content_id,
        memory_type=MemoryType.FACT,
        memory_content="Original candidate",
        memory_start_num=0,
        creator_type=Creator.USER,
        plugin_name="continuity",
    )
    test_db.add(memory)
    test_db.flush()
    snapshot = MemoriesRecord(chapter_id=chapter.chapter_id, payload=[MemorySchema.model_validate(memory)])
    pruning = {
        "action": "prune_memories",
        "config": {"model": "qwen-plus", **({} if later else {"memory_group_id": str(group.memory_group_id)})},
    }
    stages = ([{"action": "combine_chapter"}] if later else []) + [pruning, {"action": "combine_chapter"}]
    job_id = create_job(
        test_db,
        TranslationJobCreate.model_validate(
            {
                "novel_id": novel.novel_id,
                "config": {"batch_size": 10},
                "stages": stages,
            }
        ),
    )
    tasks = test_db.scalars(
        select(TranslationTask)
        .join(TranslationStage, TranslationStage.stage_id == TranslationTask.stage_id)
        .where(TranslationStage.job_id == job_id)
        .order_by(TranslationStage.stage_num)
    ).all()
    task, following = tasks[-2:]
    task_id, following_id = task.task_id, following.task_id
    batch = test_db.get(TranslationBatch, task.batch_id)
    assert batch is not None
    store = MemoryObjectStore()
    if later:
        previous = create_file(
            test_db,
            store,
            BytesIO(
                encode_translation_record(snapshot)
                + encode_translation_record(ChapterRecord(chapter_id=chapter.chapter_id, payload="Previous chapter"))
            ),
            storage_name="test",
            bucket="test",
            namespace="translations",
            content_type="application/jsonl",
        )
        test_db.flush([previous])
        tasks[0].status, tasks[0].output_file_id = State.COMPLETE, previous.file_id
        task.status = State.READY
    test_db.commit()
    monkeypatch.setattr("src.translations.actions.celery_actions.SessionLocal", testing_session_local)
    monkeypatch.setattr("src.translations.actions.prune_memories.get_object_store", lambda: store)
    client = PruningClient(response)
    monkeypatch.setitem(BATCH_CLIENT_FACTORIES, "qwen-plus", lambda: client)
    for name in ("submit", "poll", "finalize"):
        monkeypatch.setattr(app.tasks[f"src.translations.actions.prune_memories.{name}"], "apply_async", Mock())

    def check_dispatch(*args: object, **kwargs: object) -> None:
        with testing_session_local() as db:
            completed = db.get(TranslationTask, task_id)
            next_task = db.get(TranslationTask, following_id)
            assert completed is not None and completed.status == State.COMPLETE and completed.output_file_id is not None
            assert next_task is not None and next_task.status == State.READY

    dispatch = Mock(side_effect=check_dispatch)
    monkeypatch.setattr(app.tasks["src.translations.actions.combine_chapter.combine"], "apply_async", dispatch)
    if response == "prepare_upload":
        store.upload_error = ConnectionError("upload interrupted")
        with pytest.raises(ConnectionError, match="upload interrupted"):
            prepare(task_id)
        test_db.expire_all()
        assert task.input_file_id is None and batch.initial_file_id is None
        assert task.failed_at is not None and task.status == State.PREPARING
        assert test_db.scalar(select(func.count()).select_from(StoredFile)) == (1 if later else 0)
        dispatch.assert_not_called()
        return
    prepare(task_id)
    test_db.expire_all()
    assert task.status == State.PREPARED and task.input_file_id is not None
    assert (batch.initial_file_id is None) == later
    if not later:
        stored = test_db.get(StoredFile, batch.initial_file_id)
        assert stored is not None
        initial = list(iter_translation_records([store.objects[stored.object_key]]))
        assert snapshot in initial
    memory.memory_content = "Changed after preparation"
    test_db.commit()
    submit(task_id)
    assert len(client.requests) == 1
    request = client.requests[0]
    assert json.loads(request["custom_id"])["data_name"] == "memories"
    prompt = request["body"]["messages"][1]["content"]
    assert "Original candidate" in prompt and str(memory.memory_id) not in prompt
    assert ("Previous chapter" in prompt) == later
    poll(task_id)
    count_before = test_db.scalar(select(func.count()).select_from(StoredFile))
    if response in ("[99]", "[true]"):
        with pytest.raises(ValueError):
            finalize(task_id)
        test_db.expire_all()
        assert task.failed_at is not None and task.status == State.FINALIZING
        assert task.output_file_id is None and following.status == State.WAITING
        assert test_db.scalar(select(func.count()).select_from(StoredFile)) == count_before
        dispatch.assert_not_called()
    else:
        finalize(task_id)
        test_db.expire_all()
        assert task.status == State.COMPLETE and task.output_file_id is not None
        output = test_db.get(StoredFile, task.output_file_id)
        assert output is not None
        records = list(iter_translation_records([store.objects[output.object_key]]))
        assert records == [snapshot if response == "[0]" else MemoriesRecord(chapter_id=chapter.chapter_id, payload=[])]
        dispatch.assert_called_once_with((following_id,))
