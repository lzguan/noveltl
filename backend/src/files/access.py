import hashlib
import re
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import BinaryIO

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.files.async_storage import AsyncObjectStore
from src.files.exceptions import StoredFileNotFoundException
from src.files.models import StoredFile

_NAMESPACE_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62})$")
_COPY_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class UploadedFile:
    file_id: uuid.UUID
    storage_name: str
    bucket: str
    object_key: str
    content_type: str
    content_encoding: str | None
    byte_size: int
    sha256: str
    etag: str | None


async def upload_file(
    store: AsyncObjectStore,
    content: BinaryIO,
    *,
    storage_name: str,
    bucket: str,
    namespace: str,
    content_type: str,
    content_encoding: str | None = None,
) -> UploadedFile:
    if _NAMESPACE_PATTERN.fullmatch(namespace) is None:
        raise ValueError("namespace must contain only lowercase letters, numbers, and hyphens")

    file_id = uuid.uuid4()
    object_key = f"{namespace}/{file_id.hex}"
    digest = hashlib.sha256()
    byte_size = 0

    async with store.create(
        object_key,
        content_type=content_type,
        content_encoding=content_encoding,
    ) as writer:
        while chunk := content.read(_COPY_CHUNK_SIZE):
            digest.update(chunk)
            byte_size += len(chunk)
            await writer.write(chunk)

    return UploadedFile(
        file_id=file_id,
        storage_name=storage_name,
        bucket=bucket,
        object_key=object_key,
        content_type=content_type,
        content_encoding=content_encoding,
        byte_size=byte_size,
        sha256=digest.hexdigest(),
        etag=writer.result.etag,
    )


async def insert_file(db: AsyncSession, uploaded: UploadedFile) -> uuid.UUID:
    with db.no_autoflush:
        await db.execute(
            insert(StoredFile).values(
                file_id=uploaded.file_id,
                storage_name=uploaded.storage_name,
                bucket=uploaded.bucket,
                object_key=uploaded.object_key,
                content_type=uploaded.content_type,
                content_encoding=uploaded.content_encoding,
                byte_size=uploaded.byte_size,
                sha256=uploaded.sha256,
                etag=uploaded.etag,
                created_at=func.now(),
                updated_at=func.now(),
            )
        )
    return uploaded.file_id


async def get_file(db: AsyncSession, file_id: uuid.UUID) -> StoredFile:
    stored_file = await db.scalar(select(StoredFile).where(StoredFile.file_id == file_id))
    if stored_file is None:
        raise StoredFileNotFoundException(f"Stored file with ID {file_id} not found")
    return stored_file


async def fetch_file(
    store: AsyncObjectStore,
    stored_file: StoredFile,
    *,
    chunk_size: int = _COPY_CHUNK_SIZE,
) -> AsyncIterator[bytes]:
    """Fetch a recorded file's content from object storage."""
    async for chunk in store.fetch(stored_file.object_key, chunk_size=chunk_size):
        yield chunk
