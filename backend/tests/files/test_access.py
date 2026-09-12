import hashlib
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from io import BytesIO

import pytest
from sqlalchemy.orm import Session

from src.files.access import create_file, fetch_file
from src.files.models import StoredFile
from src.files.storage import ObjectWriter, UploadResult


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

    def write(self, data: str | bytes) -> int:
        encoded = data.encode() if isinstance(data, str) else data
        return self.content.write(encoded)

    def complete(self) -> None:
        self._result = UploadResult(key=self.key, etag="test-etag")


class MemoryObjectStore:
    def __init__(self, *, upload_error: Exception | None = None) -> None:
        self.upload_error = upload_error
        self.objects: dict[str, bytes] = {}
        self.fetched_keys: list[str] = []

    @contextmanager
    def create(
        self,
        key: str,
        *,
        content_type: str,
        content_encoding: str | None = None,
    ) -> Iterator[ObjectWriter]:
        writer = MemoryWriter(key)
        yield writer
        if self.upload_error is not None:
            raise self.upload_error
        self.objects[key] = writer.content.getvalue()
        writer.complete()

    def fetch(self, key: str, *, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        self.fetched_keys.append(key)
        content = self.objects[key]
        for offset in range(0, len(content), chunk_size):
            yield content[offset : offset + chunk_size]


def test_create_file_uploads_before_adding_uncommitted_metadata(test_db: Session) -> None:
    store = MemoryObjectStore()
    content = b'{"custom_id":"chapter-1"}\n'

    stored_file = create_file(
        test_db,
        store,
        BytesIO(content),
        storage_name="default",
        bucket="noveltl",
        namespace="translations",
        content_type="application/jsonl",
    )

    assert store.objects[stored_file.object_key] == content
    assert stored_file in test_db.new
    assert stored_file.byte_size == len(content)
    assert stored_file.sha256 == hashlib.sha256(content).hexdigest()
    assert stored_file.etag == "test-etag"


def test_failed_upload_does_not_add_a_file_or_rollback_the_caller(test_db: Session) -> None:
    existing = StoredFile(
        file_id=uuid.uuid4(),
        storage_name="default",
        bucket="noveltl",
        object_key="translations/existing",
        content_type="application/jsonl",
        byte_size=0,
        sha256=hashlib.sha256(b"").hexdigest(),
    )
    test_db.add(existing)
    store = MemoryObjectStore(upload_error=RuntimeError("object store unavailable"))

    with pytest.raises(RuntimeError, match="object store unavailable"):
        create_file(
            test_db,
            store,
            BytesIO(b"batch input"),
            storage_name="default",
            bucket="noveltl",
            namespace="translations",
            content_type="application/jsonl",
        )

    assert list(test_db.new) == [existing]


def test_fetch_file_resolves_the_recorded_object_key(test_db: Session) -> None:
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
    test_db.add(stored_file)
    test_db.flush()
    store.objects[stored_file.object_key] = content

    assert b"".join(fetch_file(test_db, store, stored_file.file_id, chunk_size=3)) == content
    assert store.fetched_keys == [stored_file.object_key]
