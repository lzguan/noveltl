from collections.abc import Callable
from functools import wraps
from typing import overload

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.files.access import fetch_file, get_file
from src.files.dependencies import get_async_object_store
from src.translations.actions.actions import ActionCallback, ActionTaskContext
from src.translations.jsonl import aiter_translation_records
from src.translations.models import TranslationChapterOutput, TranslationStage
from src.translations.records import ChapterRecord


@overload
def stage_chapter_outputs(callback: ActionCallback, *, stream: str = "chapter") -> ActionCallback: ...


@overload
def stage_chapter_outputs(
    callback: None = None, *, stream: str = "chapter"
) -> Callable[[ActionCallback], ActionCallback]: ...


def stage_chapter_outputs(
    callback: ActionCallback | None = None,
    *,
    stream: str = "chapter",
) -> ActionCallback | Callable[[ActionCallback], ActionCallback]:
    def decorate(fn: ActionCallback) -> ActionCallback:
        @wraps(fn)
        async def wrapped(context: ActionTaskContext) -> None:
            await fn(context)
            output_file_id = context.task.output_file_id
            if output_file_id is None:
                return

            stage_row = (
                await context.db.execute(
                    select(TranslationStage.stage_id, TranslationStage.job_id).where(
                        TranslationStage.stage_id == context.task.stage_id
                    )
                )
            ).one()
            stored_file = await get_file(context.db, output_file_id)
            await context.db.commit()

            store = get_async_object_store()
            rows = [
                {
                    "job_id": stage_row.job_id,
                    "stage_id": stage_row.stage_id,
                    "chapter_id": record.chapter_id,
                    "translated_text": record.payload,
                }
                async for record in aiter_translation_records(fetch_file(store, stored_file))
                if isinstance(record, ChapterRecord) and record.stream == stream
            ]
            if not rows:
                return

            stmt = pg_insert(TranslationChapterOutput).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=[TranslationChapterOutput.stage_id, TranslationChapterOutput.chapter_id],
                set_={
                    "translated_text": stmt.excluded.translated_text,
                    "updated_at": func.now(),
                },
            )
            await context.db.execute(stmt)

        return wrapped

    return decorate(callback) if callback is not None else decorate
