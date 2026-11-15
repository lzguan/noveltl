import asyncio
from collections.abc import Coroutine, Iterator
from typing import Any

import pytest

from src.lib.async_buffer import async_buffer


def test_runs_at_most_size_at_once_and_pulls_lazily() -> None:
    running = peak = created = 0

    async def job(value: int) -> int:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1
        return value

    def jobs() -> Iterator[Coroutine[Any, Any, int]]:
        nonlocal created
        for value in range(10):
            created += 1
            yield job(value)

    async def run() -> list[int]:
        values = []
        async for value in async_buffer(jobs(), size=3):
            values.append(value)
            # Never more than `size` awaitables pulled ahead of what was consumed.
            assert created <= len(values) + 3
        return values

    assert sorted(asyncio.run(run())) == list(range(10))
    assert peak <= 3 and created == 10


def test_yields_in_completion_order() -> None:
    async def job(value: int, delay: float) -> int:
        await asyncio.sleep(delay)
        return value

    async def run() -> list[int]:
        return [value async for value in async_buffer([job(1, 0.05), job(2, 0.0)], size=2)]

    assert asyncio.run(run()) == [2, 1]


def test_error_reaches_the_consumer_and_cancels_the_rest() -> None:
    cancelled: list[int] = []

    async def slow(value: int) -> int:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.append(value)
            raise
        return value

    async def fail() -> int:
        raise ValueError("request failed")

    async def run() -> None:
        async for _ in async_buffer([slow(1), fail(), slow(2)], size=3):
            pass

    with pytest.raises(ValueError, match="request failed"):
        asyncio.run(run())
    assert sorted(cancelled) == [1, 2]


def test_closing_early_cancels_in_flight_work() -> None:
    cancelled: list[int] = []

    async def job(value: int) -> int:
        try:
            await asyncio.sleep(0 if value == 0 else 10)
        except asyncio.CancelledError:
            cancelled.append(value)
            raise
        return value

    async def run() -> int:
        results = async_buffer([job(value) for value in range(3)], size=3)
        try:
            return await anext(results)
        finally:
            await results.aclose()

    assert asyncio.run(run()) == 0
    assert sorted(cancelled) == [1, 2]
