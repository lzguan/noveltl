from collections.abc import AsyncIterable


async def alist[T](items: AsyncIterable[T]) -> list[T]:
    return [item async for item in items]
