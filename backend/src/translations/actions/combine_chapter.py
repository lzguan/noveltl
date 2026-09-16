"""Attach pinned source chapters to the preceding stage's memories."""

from collections.abc import Iterator
from tempfile import TemporaryFile
from time import monotonic

from pydantic import TypeAdapter
from sqlalchemy import select

from src.files.access import create_file, fetch_file
from src.files.config import file_store_settings
from src.files.dependencies import get_object_store
from src.novels.models import ChapterContent
from src.translations.actions.actions import ActionTaskContext
from src.translations.actions.celery_actions import CeleryActionCallbacks
from src.translations.actions.registry import ACTION_CALLBACKS
from src.translations.celery_app import app
from src.translations.jsonl import encode_translation_record, iter_translation_records
from src.translations.models import TranslationJobChapter, TranslationStage, TranslationTask
from src.translations.records import ChapterRecord, MemoriesRecord, TranslationRecord
from src.translations.task_names import COMBINE_CHAPTER_COMBINE
from src.translations.types import ACTIONS, ActionName, TranslationTaskStatus
from src.translations.validation import validate_output_records

callbacks = CeleryActionCallbacks(app, ACTION_CALLBACKS)
_LEASE_SECONDS = 300


@callbacks.new_func(
    expect=TranslationTaskStatus.READY,
    during=TranslationTaskStatus.FINALIZING,
    finish=TranslationTaskStatus.COMPLETE,
    lease_seconds=_LEASE_SECONDS,
    name=COMBINE_CHAPTER_COMBINE,
)
def combine(context: ActionTaskContext) -> None:
    stage = context.db.get(TranslationStage, context.task.stage_id)
    if stage is None or stage.action != "combine_chapter":
        raise ValueError("Chapter combination requires a combine_chapter stage")
    if stage.stage_num == 0:
        raise ValueError("combine_chapter requires a previous stage's memories output")
    previous, previous_stage = (
        context.db.execute(
            select(TranslationTask, TranslationStage)
            .join(TranslationStage, TranslationStage.stage_id == TranslationTask.stage_id)
            .where(
                TranslationTask.batch_id == context.task.batch_id,
                TranslationStage.job_id == stage.job_id,
                TranslationStage.stage_num == stage.stage_num - 1,
            )
        )
        .one()
        ._t
    )
    if (
        previous.status != TranslationTaskStatus.COMPLETE
        or previous.failed_at is not None
        or previous.output_file_id is None
    ):
        raise ValueError("Previous translation task must have a completed output artifact")
    signature = ACTIONS[TypeAdapter(ActionName).validate_python(previous_stage.action)]
    if not ACTIONS["combine_chapter"].input_types <= signature.output_types:
        raise ValueError("Previous stage must produce memories")
    chapter_ids = list(
        context.db.scalars(
            select(TranslationJobChapter.chapter_id).where(
                TranslationJobChapter.job_id == stage.job_id,
                TranslationJobChapter.batch_id == context.task.batch_id,
            )
        )
    )
    if not chapter_ids:
        raise ValueError("Cannot combine an empty translation batch")
    store = get_object_store()

    def records() -> Iterator[TranslationRecord]:
        previous_records = iter_translation_records(fetch_file(context.db, store, previous.output_file_id))
        for record in validate_output_records(
            previous_records, chapter_ids=chapter_ids, output_types=signature.output_types
        ):
            if isinstance(record, MemoriesRecord):
                yield record
        rows = context.db.execute(
            select(TranslationJobChapter.chapter_id, ChapterContent.chapter_content_text)
            .join(ChapterContent, ChapterContent.chapter_content_id == TranslationJobChapter.source_chapter_content_id)
            .where(
                TranslationJobChapter.job_id == stage.job_id,
                TranslationJobChapter.batch_id == context.task.batch_id,
            )
            .execution_options(yield_per=100)
        )
        for chapter_id, text in rows:
            yield ChapterRecord(chapter_id=chapter_id, payload=text)

    validated = validate_output_records(
        records(),
        chapter_ids=chapter_ids,
        output_types=ACTIONS["combine_chapter"].output_types,
    )
    renew_at = monotonic() + _LEASE_SECONDS / 3
    with TemporaryFile(mode="w+b") as content:
        for record in validated:
            content.write(encode_translation_record(record))
            if monotonic() >= renew_at:
                context.renew_lease()
                renew_at = monotonic() + _LEASE_SECONDS / 3
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
        context.db.flush([stored_file])
        context.task.output_file_id = stored_file.file_id
