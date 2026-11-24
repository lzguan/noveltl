import hashlib
import re
import uuid
from collections.abc import AsyncIterator
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.files.async_storage import AsyncObjectStore
from src.files.exceptions import StoredFileNotFoundException
from src.files.models import StoredFile

_NAMESPACE_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62})$")
_COPY_CHUNK_SIZE = 1024 * 1024


async def create_file(
    db: AsyncSession,
    store: AsyncObjectStore,
    content: BinaryIO,
    *,
    storage_name: str,
    bucket: str,
    namespace: str,
    content_type: str,
    content_encoding: str | None = None,
) -> StoredFile:
    """Upload a file and add its completed metadata to the caller's transaction."""
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

    stored_file = StoredFile(
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
    db.add(stored_file)
    return stored_file


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
