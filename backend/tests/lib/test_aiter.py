import asyncio

import pytest

from src.lib.aiter import achain, agroupby, as_async_iter, azip_longest


def _collect(iterator) -> list:
    async def run() -> list:
        return [item async for item in iterator]

    return asyncio.run(run())


def test_achain_yields_each_iterable_in_order() -> None:
    assert _collect(achain(as_async_iter([1, 2]), as_async_iter([]), as_async_iter([3]))) == [1, 2, 3]


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ([1, 2], ["a", "b"], [(1, "a"), (2, "b")]),
        ([1, 2, 3], ["a"], [(1, "a"), (2, None), (3, None)]),
        ([], ["a", "b"], [(None, "a"), (None, "b")]),
        ([], [], []),
    ],
)
def test_azip_longest_pads_the_shorter_side(first: list, second: list, expected: list) -> None:
    assert _collect(azip_longest(as_async_iter(first), as_async_iter(second))) == expected


def test_agroupby_groups_consecutive_items_like_itertools() -> None:
    items = [("a", 1), ("a", 2), ("b", 3), ("a", 4)]
    assert _collect(agroupby(as_async_iter(items), key=lambda item: item[0])) == [
        ("a", [("a", 1), ("a", 2)]),
        ("b", [("b", 3)]),
        ("a", [("a", 4)]),
    ]
    assert _collect(agroupby(as_async_iter([]), key=lambda item: item)) == []
