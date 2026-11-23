from collections.abc import AsyncIterable, AsyncIterator, Callable, Iterable


async def as_async_iter[T](items: Iterable[T]) -> AsyncIterator[T]:
    for item in items:
        yield item


async def achain[T](*iterables: AsyncIterable[T]) -> AsyncIterator[T]:
    for iterable in iterables:
        async for item in iterable:
            yield item


async def azip_longest[A, B](
    first: AsyncIterable[A], second: AsyncIterable[B]
) -> AsyncIterator[tuple[A | None, B | None]]:
    first_iter, second_iter = aiter(first), aiter(second)
    first_done = second_done = False
    while True:
        a = b = None
        if not first_done:
            try:
                a = await anext(first_iter)
            except StopAsyncIteration:
                first_done = True
        if not second_done:
            try:
                b = await anext(second_iter)
            except StopAsyncIteration:
                second_done = True
        if first_done and second_done:
            return
        yield a, b


async def agroupby[T, K](items: AsyncIterable[T], key: Callable[[T], K]) -> AsyncIterator[tuple[K, list[T]]]:
    # Like itertools.groupby over consecutive items, but each group arrives as a list.
    pending: tuple[K, list[T]] | None = None
    async for item in items:
        item_key = key(item)
        if pending is not None and pending[0] == item_key:
            pending[1].append(item)
            continue
        if pending is not None:
            yield pending
        pending = (item_key, [item])
    if pending is not None:
        yield pending
