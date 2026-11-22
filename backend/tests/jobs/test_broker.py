import asyncio
import os
import uuid

import pytest
from redis.asyncio import Redis

from src.jobs.broker import make_jobs_broker


@pytest.fixture
def test_redis_url() -> str:
    host, port = os.getenv("TEST_REDIS_HOST"), os.getenv("TEST_REDIS_PORT")
    if not host or not port:
        pytest.skip("TEST_REDIS_HOST and TEST_REDIS_PORT are not set")
    return f"redis://{host}:{port}/0"


async def test_the_first_worker_receives_tasks_enqueued_before_it_started(test_redis_url: str) -> None:
    queue_name = f"jobs-test-{uuid.uuid4()}"
    broker = make_jobs_broker(test_redis_url, queue_name)

    @broker.task(task_name="jobs_test.noop")
    async def noop(value: str) -> None: ...

    try:
        await noop.kiq("sent before any consumer group existed")
        await broker.startup()  # the worker side creates the consumer group here
        message = await asyncio.wait_for(anext(broker.listen()), timeout=10)
        assert b"sent before any consumer group existed" in message.data
    finally:
        await broker.shutdown()
        async with Redis.from_url(test_redis_url) as redis:
            await redis.delete(queue_name)
