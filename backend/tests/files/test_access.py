import hashlib
import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from io import BytesIO

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.files.access import create_file, fetch_file
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


async def test_create_file_uploads_before_adding_uncommitted_metadata(async_test_db: AsyncSession) -> None:
    store = MemoryObjectStore()
    content = b'{"custom_id":"chapter-1"}\n'

    stored_file = await create_file(
        async_test_db,
        store,
        BytesIO(content),
        storage_name="default",
        bucket="noveltl",
        namespace="translations",
        content_type="application/jsonl",
    )

    assert store.objects[stored_file.object_key] == content
    assert stored_file in async_test_db.new
    assert stored_file.byte_size == len(content)
    assert stored_file.sha256 == hashlib.sha256(content).hexdigest()
    assert stored_file.etag == "test-etag"


async def test_failed_upload_does_not_add_a_file_or_rollback_the_caller(async_test_db: AsyncSession) -> None:
    existing = StoredFile(
        file_id=uuid.uuid4(),
        storage_name="default",
        bucket="noveltl",
        object_key="translations/existing",
        content_type="application/jsonl",
        byte_size=0,
        sha256=hashlib.sha256(b"").hexdigest(),
    )
    async_test_db.add(existing)
    store = MemoryObjectStore(upload_error=RuntimeError("object store unavailable"))

    with pytest.raises(RuntimeError, match="object store unavailable"):
        await create_file(
            async_test_db,
            store,
            BytesIO(b"batch input"),
            storage_name="default",
            bucket="noveltl",
            namespace="translations",
            content_type="application/jsonl",
        )

    assert list(async_test_db.new) == [existing]


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
