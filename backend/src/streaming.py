"""Adapters between chunk iterators and the file-like objects libraries expect."""

import io
from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from _typeshed import WriteableBuffer


class IterReader(io.RawIOBase):
    """Read-only file-like view over an iterable of byte chunks.

    Bridges producers that yield chunks, such as `ObjectStore.fetch`, to
    consumers that call `read`, without buffering the whole stream.

    Prefer `buffered_reader` when handing the stream to a library. A raw read
    stops at a chunk boundary and returns short, as a raw stream may, and this
    class is not an `IO[bytes]` for the purposes of type checking; wrapping it
    in a `BufferedReader` fixes both.

    Unseekable, so a consumer cannot discover the length up front. HTTP clients
    fall back to chunked transfer encoding for a body of unknown length, which
    some servers reject for uploads; buffer to a temporary file when a
    `Content-Length` is required. Closing also closes the underlying iterator
    if it is closeable, releasing whatever the producer holds open.
    """

    def __init__(self, chunks: Iterable[bytes]) -> None:
        self._chunks = iter(chunks)
        self._pending = b""

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: "WriteableBuffer") -> int:
        # Skip empty chunks; returning 0 for one would signal end of stream.
        while not self._pending:
            try:
                self._pending = next(self._chunks)
            except StopIteration:
                return 0
        target = memoryview(buffer).cast("B")
        size = min(len(target), len(self._pending))
        target[:size] = self._pending[:size]
        self._pending = self._pending[size:]
        return size

    def close(self) -> None:
        try:
            closer = getattr(self._chunks, "close", None)
            if closer is not None:
                closer()
        finally:
            self._pending = b""
            super().close()


def buffered_reader(chunks: Iterable[bytes], *, buffer_size: int = io.DEFAULT_BUFFER_SIZE) -> io.BufferedReader:
    """Wrap chunks as a buffered binary stream over `IterReader`.

    Reads span chunk boundaries and the result satisfies `IO[bytes]`, so this is
    what callers hand to libraries that take a file object.
    """
    return io.BufferedReader(IterReader(chunks), buffer_size=buffer_size)
