import asyncio
import threading
import uuid
from unittest.mock import AsyncMock, Mock

import pytest

from src.database import SessionLocal
from src.memory.agent.celery_app import app
from src.memory.agent.dispatch.celery import (
    CeleryMemoryAgentDispatcher,
    run_memory_job,
    run_memory_task,
)
from src.memory.exceptions import MemoryAgentEnqueueFailedException


def test_dispatcher_publishes_json_safe_job_and_task_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    job_apply_async = Mock()
    task_apply_async = Mock()
    monkeypatch.setattr(run_memory_job, "apply_async", job_apply_async)
    monkeypatch.setattr(run_memory_task, "apply_async", task_apply_async)
    memory_job_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    dispatcher = CeleryMemoryAgentDispatcher()

    dispatcher.enqueue_job(memory_job_id)
    dispatcher.enqueue_task(memory_job_id, chapter_id)

    job_apply_async.assert_called_once_with((str(memory_job_id),), task_id=str(memory_job_id))
    task_apply_async.assert_called_once_with(
        (str(memory_job_id), str(chapter_id)),
        task_id=f"{memory_job_id}:{chapter_id}",
    )


def test_dispatcher_translates_publish_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_memory_job, "apply_async", Mock(side_effect=RuntimeError("broker unavailable")))

    with pytest.raises(MemoryAgentEnqueueFailedException, match="broker unavailable"):
        CeleryMemoryAgentDispatcher().enqueue_job(uuid.uuid4())


def test_async_dispatch_runs_sync_publish_on_worker_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    dispatcher = CeleryMemoryAgentDispatcher()
    memory_job_id = uuid.uuid4()
    event_loop_thread = threading.get_ident()
    received: list[tuple[uuid.UUID, int]] = []

    def recording_enqueue(received_job_id: uuid.UUID) -> None:
        received.append((received_job_id, threading.get_ident()))

    monkeypatch.setattr(dispatcher, "enqueue_job", recording_enqueue)

    asyncio.run(dispatcher.aenqueue_job(memory_job_id))

    assert received[0][0] == memory_job_id
    assert received[0][1] != event_loop_thread


def test_worker_entries_reconstruct_ids_and_run_async_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    received_jobs: list[tuple[object, uuid.UUID]] = []

    async def run_all_tasks(db_factory: object, memory_job_id: uuid.UUID):
        received_jobs.append((db_factory, memory_job_id))
        if False:
            yield

    run_task = AsyncMock()
    monkeypatch.setattr("src.memory.agent.dispatch.celery.run_all_tasks", run_all_tasks)
    monkeypatch.setattr("src.memory.agent.dispatch.celery.run_task", run_task)
    memory_job_id = uuid.uuid4()
    chapter_id = uuid.uuid4()

    run_memory_job(str(memory_job_id))
    run_memory_task(str(memory_job_id), str(chapter_id))

    assert received_jobs == [(SessionLocal, memory_job_id)]
    run_task.assert_awaited_once_with(SessionLocal, memory_job_id, chapter_id)


def test_worker_configuration_registers_dispatch_tasks() -> None:
    assert app.conf.include == ["src.memory.agent.dispatch.celery"]
    assert app.conf.worker_pool == "threads"
    assert app.conf.worker_concurrency == 2
    assert app.conf.worker_prefetch_multiplier == 1
