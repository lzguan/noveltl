import hashlib
import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from io import BytesIO

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.files.access import fetch_file, get_file, insert_file, upload_file
from src.files.async_storage import AsyncObjectWriter
from src.files.models import StoredFile
from src.files.storage import UploadResult
from test_support.aiter import alist


class MemoryWriter:
    def __init__(self, key: str) -> None:
        self.key = key
        self.content = BytesIO()
        self._result: UploadResult | None = None

    @property
    def result(self) -> UploadResult:
        if self._result is None:
            raise RuntimeError("upload is incomplete")
        return self._result

    async def write(self, data: str | bytes) -> int:
        encoded = data.encode() if isinstance(data, str) else data
        return self.content.write(encoded)

    def complete(self) -> None:
        self._result = UploadResult(key=self.key, etag="test-etag")


class MemoryObjectStore:
    def __init__(self, *, upload_error: Exception | None = None) -> None:
        self.upload_error = upload_error
        self.objects: dict[str, bytes] = {}
        self.fetched_keys: list[str] = []

    @asynccontextmanager
    async def create(
        self,
        key: str,
        *,
        content_type: str,
        content_encoding: str | None = None,
    ) -> AsyncGenerator[AsyncObjectWriter]:
        writer = MemoryWriter(key)
        yield writer
        if self.upload_error is not None:
            raise self.upload_error
        self.objects[key] = writer.content.getvalue()
        writer.complete()

    async def fetch(self, key: str, *, chunk_size: int = 1024 * 1024) -> AsyncIterator[bytes]:
        self.fetched_keys.append(key)
        content = self.objects[key]
        for offset in range(0, len(content), chunk_size):
            yield content[offset : offset + chunk_size]


async def test_failed_upload_raises_without_recording_an_object() -> None:
    store = MemoryObjectStore(upload_error=RuntimeError("object store unavailable"))

    with pytest.raises(RuntimeError, match="object store unavailable"):
        await upload_file(
            store,
            BytesIO(b"batch input"),
            storage_name="default",
            bucket="noveltl",
            namespace="translations",
            content_type="application/jsonl",
        )

    assert store.objects == {}


async def test_fetch_file_reads_the_recorded_object_key(async_test_db: AsyncSession) -> None:
    store = MemoryObjectStore()
    content = b"batch output"
    stored_file = StoredFile(
        file_id=uuid.uuid4(),
        storage_name="default",
        bucket="noveltl",
        object_key="translations/output",
        content_type="application/jsonl",
        byte_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )
    async_test_db.add(stored_file)
    await async_test_db.flush()
    store.objects[stored_file.object_key] = content

    assert b"".join(await alist(fetch_file(store, stored_file, chunk_size=3))) == content
    assert store.fetched_keys == [stored_file.object_key]


async def test_upload_file_and_insert_file_separates_storage_from_db_insert(async_test_db: AsyncSession) -> None:
    store = MemoryObjectStore()
    content = b'{"chapter":1}\n'

    uploaded = await upload_file(
        store,
        BytesIO(content),
        storage_name="default",
        bucket="noveltl",
        namespace="translations",
        content_type="application/jsonl",
    )
    assert store.objects[uploaded.object_key] == content
    assert uploaded.byte_size == len(content)
    assert uploaded.sha256 == hashlib.sha256(content).hexdigest()
    assert uploaded.etag == "test-etag"
    assert list(async_test_db.new) == []

    file_id = await insert_file(async_test_db, uploaded)
    assert file_id == uploaded.file_id
    assert list(async_test_db.new) == []
    with async_test_db.no_autoflush:
        recorded = await get_file(async_test_db, file_id)
    assert recorded.object_key == uploaded.object_key
    assert recorded.sha256 == hashlib.sha256(content).hexdigest()
    assert recorded.byte_size == len(content)
    assert recorded.etag == "test-etag"
