import os
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from taskiq import InMemoryBroker, ScheduledTask, ScheduleSource
from taskiq_redis import ListRedisScheduleSource

from src.translations.actions.actions import ActionTaskContext
from src.translations.actions.execution.taskiq_actions import TaskiqActionCallbacks
from src.translations.models import TranslationTask
from src.translations.types import TranslationTaskStatus as State
from tests.translations.test_claims import next_task_id, task_id  # noqa: F401  fixtures


class RecordingSource(ScheduleSource):
    def __init__(self) -> None:
        self.added: list[ScheduledTask] = []

    async def get_schedules(self) -> list[ScheduledTask]:
        return []

    async def add_schedule(self, schedule: ScheduledTask) -> None:
        self.added.append(schedule)


@pytest.fixture
async def broker(
    testing_async_session_local: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[InMemoryBroker]:
    monkeypatch.setattr(
        "src.translations.actions.execution.taskiq_actions.TaskiqSessionLocal", testing_async_session_local
    )
    # Kicks run the task in place, so a chain completes before kiq returns.
    broker = InMemoryBroker(await_inplace=True)
    await broker.startup()
    try:
        yield broker
    finally:
        await broker.shutdown()


async def test_wrapper_commits_before_running_next_step(
    task_id: UUID,  # noqa: F811
    broker: InMemoryBroker,
    testing_async_session_local: async_sessionmaker[AsyncSession],
) -> None:
    callbacks = TaskiqActionCallbacks(broker, RecordingSource(), {})
    calls = []

    @callbacks.new_func(expect=State.READY, during=State.PREPARING, finish=State.PREPARED, name="test.first")
    async def first(context: ActionTaskContext) -> None:
        context.task.provider_batch_id = "committed"

    @callbacks.new_func(expect=State.PREPARED, during=State.FINALIZING, finish=State.COMPLETE, name="test.second")
    async def second(context: ActionTaskContext) -> None:
        assert context.task.provider_batch_id == "committed"
        calls.append(context.task.task_id)

    await callbacks.entrypoint(task_id)
    await callbacks.entrypoint(task_id)
    assert calls == [task_id]
    async with testing_async_session_local() as db:
        task = await db.get(TranslationTask, task_id)
        assert task is not None
        assert task.status == State.COMPLETE and task.claim_token is None


async def test_step_starts_without_a_connection_and_reads_release_theirs(
    task_id: UUID,  # noqa: F811
    broker: InMemoryBroker,
) -> None:
    # Steps await providers and the object store; the session must not hold a
    # connection (or an open transaction) across that I/O.
    callbacks = TaskiqActionCallbacks(broker, RecordingSource(), {})
    observed: list[bool] = []

    @callbacks.new_func(expect=State.READY, during=State.PREPARING, finish=State.PREPARED, name="test.release")
    async def step(context: ActionTaskContext) -> None:
        observed.append(context.db.in_transaction())
        await context.db.scalar(select(func.clock_timestamp()))
        observed.append(context.db.in_transaction())
        await context.db.commit()
        observed.append(context.db.in_transaction())
        context.task.provider_batch_id = "staged after the last read"

    await callbacks.entrypoint(task_id)
    assert observed == [False, True, False]


async def test_wrapper_failure_rolls_back_and_blocks_retry(
    task_id: UUID,  # noqa: F811
    broker: InMemoryBroker,
    testing_async_session_local: async_sessionmaker[AsyncSession],
) -> None:
    callbacks = TaskiqActionCallbacks(broker, RecordingSource(), {})
    calls = []

    @callbacks.new_func(expect=State.READY, during=State.PREPARING, finish=State.PREPARED, name="test.failing")
    async def failing(context: ActionTaskContext) -> None:
        calls.append(context.task.task_id)
        context.task.provider_batch_id = "rolled-back"
        raise ValueError("failed preparation")

    # A worker logs a step's exception; the task row records it.
    await callbacks.entrypoint(task_id)
    await callbacks.entrypoint(task_id)
    assert calls == [task_id]
    async with testing_async_session_local() as db:
        task = await db.get(TranslationTask, task_id)
        assert task is not None
        assert task.provider_batch_id is None and task.status == State.PREPARING
        assert task.failed_at is not None and task.error == "failed preparation"


async def test_pending_poll_is_scheduled_after_its_interval_instead_of_kicked(
    task_id: UUID,  # noqa: F811
    broker: InMemoryBroker,
    testing_async_session_local: async_sessionmaker[AsyncSession],
) -> None:
    source = RecordingSource()
    callbacks = TaskiqActionCallbacks(broker, source, {})
    polls = []

    @callbacks.new_poll(expect=State.READY, during=State.PROCESSING, finish=State.PROCESSED, name="test.poll")
    async def poll(context: ActionTaskContext) -> bool:
        polls.append(context.task.task_id)
        return False

    before = datetime.now(UTC)
    await callbacks.entrypoint(task_id)
    after = datetime.now(UTC)
    assert polls == [task_id]
    (scheduled,) = source.added
    assert scheduled.task_name == "test.poll" and scheduled.args == [str(task_id)]
    assert scheduled.time is not None
    assert before + timedelta(seconds=60) <= scheduled.time <= after + timedelta(seconds=60)
    async with testing_async_session_local() as db:
        task = await db.get(TranslationTask, task_id)
        assert task is not None and task.status == State.READY and task.next_poll_at is not None


async def test_recovery_dispatch_sends_due_polls_at_once_and_schedules_later_ones(
    task_id: UUID,  # noqa: F811
    broker: InMemoryBroker,
    testing_async_session_local: async_sessionmaker[AsyncSession],
) -> None:
    source = RecordingSource()
    callbacks = TaskiqActionCallbacks(broker, source, {})
    polls = []

    @callbacks.new_poll(expect=State.READY, during=State.PROCESSING, finish=State.PROCESSED, name="test.recover")
    async def poll(context: ActionTaskContext) -> bool:
        polls.append(context.task.task_id)
        return True

    step = callbacks.resume_step(State.READY)
    assert step is not None
    await step.dispatch(task_id, delay=timedelta(minutes=5))
    assert polls == [] and len(source.added) == 1
    await step.dispatch(task_id, delay=timedelta(seconds=-1))
    assert polls == [task_id] and len(source.added) == 1


async def test_exitpoint_starts_the_next_action_after_committing_it_ready(
    task_id: UUID,  # noqa: F811
    next_task_id: UUID,  # noqa: F811
    broker: InMemoryBroker,
    testing_async_session_local: async_sessionmaker[AsyncSession],
) -> None:
    started: list[UUID] = []

    class NextAction(TaskiqActionCallbacks):
        async def entrypoint(self, x: UUID) -> None:
            async with testing_async_session_local() as db:
                task = await db.get(TranslationTask, x)
                assert task is not None and task.status == State.READY
            started.append(x)

    callbacks = TaskiqActionCallbacks(
        broker, RecordingSource(), {"prune_memories": NextAction(broker, RecordingSource(), {})}
    )
    async with testing_async_session_local.begin() as db:
        await db.execute(
            update(TranslationTask).where(TranslationTask.task_id == task_id).values(status=State.COMPLETE)
        )
    await callbacks.exitpoint(task_id)
    assert started == [next_task_id]


@pytest.fixture
def test_redis_url() -> str:
    host, port = os.getenv("TEST_REDIS_HOST"), os.getenv("TEST_REDIS_PORT")
    if not host or not port:
        pytest.skip("TEST_REDIS_HOST and TEST_REDIS_PORT are not set")
    return f"redis://{host}:{port}/0"


async def test_schedule_source_rereads_past_minutes_on_every_reload(test_redis_url: str) -> None:
    # The list source buckets one-off schedules by minute and a reload reads the current
    # minute. A poll scheduled into a minute after its last reload is only delivered
    # because each reload also rereads earlier buckets; an upgrade must keep that.
    prefix = f"translations-schedules-test-{uuid.uuid4()}"
    source = ListRedisScheduleSource(test_redis_url, prefix=prefix)
    await source.startup()
    try:
        assert await source.get_schedules() == []
        schedule = ScheduledTask(
            task_name="test.poll",
            labels={},
            args=["task"],
            kwargs={},
            time=datetime.now(UTC) - timedelta(minutes=2),
        )
        await source.add_schedule(schedule)
        assert [s.schedule_id for s in await source.get_schedules()] == [schedule.schedule_id]
        assert [s.schedule_id for s in await source.get_schedules()] == [schedule.schedule_id]
        await source.post_send(schedule)
        assert await source.get_schedules() == []
    finally:
        await source.shutdown()
        async with Redis.from_url(test_redis_url) as redis:
            keys = [key async for key in redis.scan_iter(f"{prefix}:*")]
            if keys:
                await redis.delete(*keys)
