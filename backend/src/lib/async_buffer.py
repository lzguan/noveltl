import asyncio
from collections.abc import AsyncGenerator, AsyncIterable, Awaitable, Iterable

from src.lib.aiter import as_async_iter


async def async_buffer[T](
    awaitables: Iterable[Awaitable[T]] | AsyncIterable[Awaitable[T]], size: int = 8
) -> AsyncGenerator[T]:
    # Runs at most `size` awaitables at once, counting finished results the consumer has
    # not taken yet, and pulls the next awaitable only when there is room. Results come
    # out in completion order. An error is raised to the consumer; closing early or
    # failing cancels whatever is still running.
    if size <= 0:
        raise ValueError("size must be positive")
    pending: set[asyncio.Future[T]] = set()
    try:
        source = awaitables if isinstance(awaitables, AsyncIterable) else as_async_iter(awaitables)
        async for awaitable in source:
            pending.add(asyncio.ensure_future(awaitable))
            if len(pending) >= size:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    yield task.result()
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                yield task.result()
    finally:
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
