import asyncio
from collections.abc import AsyncIterator

import pytest

from src.lib.async_bridge import iterate_sync, run_sync


async def _loop_id() -> int:
    return id(asyncio.get_running_loop())


def test_run_sync_returns_results_and_reuses_one_loop() -> None:
    assert run_sync(asyncio.sleep(0, result="value")) == "value"
    assert run_sync(_loop_id()) == run_sync(_loop_id())


def test_run_sync_propagates_errors() -> None:
    async def fail() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        run_sync(fail())


def test_iterate_sync_yields_on_demand_and_propagates_errors() -> None:
    produced: list[int] = []

    async def source() -> AsyncIterator[int]:
        for value in (1, 2):
            produced.append(value)
            yield value
        raise ConnectionError("download interrupted")

    iterator = iterate_sync(source())
    assert next(iterator) == 1
    assert produced == [1]  # nothing is fetched ahead of the consumer
    assert next(iterator) == 2
    with pytest.raises(ConnectionError, match="download interrupted"):
        next(iterator)


def test_closing_early_closes_the_async_source() -> None:
    closed = False

    async def source() -> AsyncIterator[int]:
        nonlocal closed
        try:
            for value in range(10):
                yield value
        finally:
            closed = True

    iterator = iterate_sync(source())
    assert next(iterator) == 0
    iterator.close()
    assert closed


def test_iterate_sync_works_from_a_running_loop_in_another_thread() -> None:
    async def source() -> AsyncIterator[int]:
        yield 1
        yield 2

    async def consume() -> list[int]:
        return await asyncio.to_thread(lambda: list(iterate_sync(source())))

    assert asyncio.run(consume()) == [1, 2]
