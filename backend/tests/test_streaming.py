import io
from collections.abc import Iterator

import pytest

from src.streaming import IterReader, buffered_reader


def test_raw_read_stops_at_a_chunk_boundary_but_skips_empty_chunks() -> None:
    # A raw stream may return short; only an empty result means end of stream.
    reader = IterReader([b"abc", b"", b"de", b"fgh"])
    assert reader.read(4) == b"abc"
    assert reader.read(4) == b"de"
    assert reader.read() == b"fgh"
    assert reader.read() == b""


def test_buffered_reads_span_chunk_boundaries() -> None:
    assert buffered_reader([b"abc", b"", b"de", b"fgh"]).read(4) == b"abcd"


def test_partial_reads_do_not_lose_the_rest_of_a_chunk() -> None:
    reader = IterReader([b"abcdef"])
    assert [reader.read(2) for _ in range(3)] == [b"ab", b"cd", b"ef"]
    assert reader.read(2) == b""


def test_chunks_are_pulled_lazily() -> None:
    pulled: list[int] = []

    def chunks() -> Iterator[bytes]:
        for index in range(3):
            pulled.append(index)
            yield b"xy"

    reader = IterReader(chunks())
    assert reader.read(2) == b"xy"
    assert pulled == [0]
    assert reader.read(2) == b"xy"
    assert pulled == [0, 1]


def test_close_releases_the_producer() -> None:
    closed = False

    def chunks() -> Iterator[bytes]:
        nonlocal closed
        try:
            yield b"payload"
        finally:
            closed = True

    reader = IterReader(chunks())
    assert reader.read(3) == b"pay"
    reader.close()
    assert closed and reader.closed


def test_buffered_reader_supports_line_access_and_is_not_seekable() -> None:
    reader = buffered_reader([b"first\nsec", b"ond\n"])
    assert isinstance(reader, io.BufferedReader)
    assert reader.readlines() == [b"first\n", b"second\n"]
    assert not reader.seekable()
    with pytest.raises(OSError):
        reader.seek(0)
