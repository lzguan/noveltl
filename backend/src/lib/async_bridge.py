import asyncio
import os
import threading
from collections.abc import AsyncIterable, AsyncIterator, Coroutine, Generator
from typing import Any

# Stopgap until the steps are async: sync code calls async clients through one event
# loop per process, running on its own daemon thread. The default loop does not work
# here: worker threads (Celery tasks, asyncio.to_thread) have none, a loop that is
# already running (the in-process eval runner's) cannot be blocked on from sync code,
# and a loop per thread or per asyncio.run call would break cached async clients,
# whose HTTP connection pools bind to the loop they first run on. The loop starts on
# first use; _lock stops two threads creating it at once, and _loop_pid restarts it
# in a forked child, which inherits the loop object but not the thread running it.
_lock = threading.Lock()
_loop: asyncio.AbstractEventLoop | None = None
_loop_pid: int | None = None


def _bridge_loop() -> asyncio.AbstractEventLoop:
    global _loop, _loop_pid
    with _lock:
        # A forked child inherits the loop object but not its thread; start a fresh one.
        if _loop is None or _loop.is_closed() or _loop_pid != os.getpid():
            loop = asyncio.new_event_loop()
            threading.Thread(target=loop.run_forever, name="async-bridge", daemon=True).start()
            _loop, _loop_pid = loop, os.getpid()
        return _loop


def run_sync[T](coroutine: Coroutine[Any, Any, T]) -> T:
    loop = _bridge_loop()
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is loop:
        coroutine.close()
        raise RuntimeError("run_sync cannot be called from the bridge loop itself")
    return asyncio.run_coroutine_threadsafe(coroutine, loop).result()


async def _next[T](iterator: AsyncIterator[T]) -> T:
    return await anext(iterator)


async def _close(iterator: AsyncIterator[Any]) -> None:
    aclose = getattr(iterator, "aclose", None)
    if aclose is not None:
        await aclose()


def iterate_sync[T](source: AsyncIterable[T]) -> Generator[T]:
    # Pull one item per request: nothing is fetched ahead of the consumer.
    iterator = aiter(source)
    try:
        while True:
            try:
                item = run_sync(_next(iterator))
            except StopAsyncIteration:
                return
            yield item
    finally:
        # Closing early (or a consumer error) releases whatever the source holds open.
        run_sync(_close(iterator))
