from collections.abc import AsyncIterable
from tempfile import TemporaryFile
from uuid import UUID

from src.files.access import insert_file, upload_file
from src.files.async_storage import AsyncObjectStore
from src.files.config import file_store_settings
from src.translations.actions.actions import ActionTaskContext


async def store_lines(context: ActionTaskContext, store: AsyncObjectStore, lines: AsyncIterable[bytes]) -> UUID:
    with TemporaryFile(mode="w+b") as content:
        async for line in lines:
            content.write(line)
        await context.db.commit()
        content.seek(0)
        uploaded = await upload_file(
            store,
            content,
            storage_name=file_store_settings.FILE_STORE_NAME,
            bucket=file_store_settings.S3_BUCKET,
            namespace="translations",
            content_type="application/jsonl",
        )
        file_id = await insert_file(context.db, uploaded)
        await context.db.commit()
        return file_id
