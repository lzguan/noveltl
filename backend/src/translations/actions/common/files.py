from collections.abc import Iterable
from tempfile import TemporaryFile
from time import monotonic
from uuid import UUID

from src.files.access import create_file
from src.files.config import file_store_settings
from src.files.storage import ObjectStore
from src.translations.actions.actions import ActionTaskContext


def store_lines(
    context: ActionTaskContext, store: ObjectStore, lines: Iterable[bytes], *, renew_seconds: float
) -> UUID:
    renew_at = monotonic() + renew_seconds
    with TemporaryFile(mode="w+b") as content:
        for line in lines:
            content.write(line)
            if monotonic() >= renew_at:
                context.renew_lease()
                renew_at = monotonic() + renew_seconds
        # The upload is one blocking call, so it starts with a fresh lease.
        context.renew_lease()
        content.seek(0)
        stored_file = create_file(
            context.db,
            store,
            content,
            storage_name=file_store_settings.FILE_STORE_NAME,
            bucket=file_store_settings.S3_BUCKET,
            namespace="translations",
            content_type="application/jsonl",
        )
        context.db.flush()
        return stored_file.file_id
