from collections.abc import AsyncIterable
from tempfile import TemporaryFile
from time import monotonic
from uuid import UUID

from src.files.access import create_file
from src.files.async_storage import AsyncObjectStore
from src.files.config import file_store_settings
from src.translations.actions.actions import ActionTaskContext


async def store_lines(
    context: ActionTaskContext, store: AsyncObjectStore, lines: AsyncIterable[bytes], *, renew_seconds: float
) -> UUID:
    renew_at = monotonic() + renew_seconds
    with TemporaryFile(mode="w+b") as content:
        async for line in lines:
            content.write(line)
            if monotonic() >= renew_at:
                await context.renew_lease()
                renew_at = monotonic() + renew_seconds
        # The upload is one awaited operation, so it starts with a fresh lease.
        await context.renew_lease()
        content.seek(0)
        stored_file = await create_file(
            context.db,
            store,
            content,
            storage_name=file_store_settings.FILE_STORE_NAME,
            bucket=file_store_settings.S3_BUCKET,
            namespace="translations",
            content_type="application/jsonl",
        )
        await context.db.flush()
        return stored_file.file_id
