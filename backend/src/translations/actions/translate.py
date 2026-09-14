"""Plain translation preparation, independent of the inference provider."""

from collections.abc import Iterator
from tempfile import TemporaryFile
from time import monotonic
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy import select

from src.files.access import create_file, fetch_file
from src.files.config import file_store_settings
from src.files.dependencies import get_object_store
from src.files.storage import ObjectStore
from src.novels.models import ChapterContent
from src.translations.actions.actions import ActionTaskContext
from src.translations.actions.celery_actions import CeleryActionCallbacks
from src.translations.actions.registry import ACTION_CALLBACKS
from src.translations.batch_lines import BatchItem, InferenceMessage, InferenceRequest
from src.translations.celery_app import app
from src.translations.codecs.registry import get_codec
from src.translations.jsonl import iter_translation_records
from src.translations.models import TranslationJobChapter, TranslationStage, TranslationTask
from src.translations.records import ChapterRecord
from src.translations.schemas import TranslateConfig
from src.translations.types import ACTIONS, ActionName, TranslationTaskStatus
from src.translations.validation import validate_output_records


def _chapter_inputs(
    context: ActionTaskContext, store: ObjectStore, stage: TranslationStage, chapter_ids: list[UUID]
) -> Iterator[ChapterRecord]:
    if stage.stage_num == 0:
        rows = context.db.execute(
            select(TranslationJobChapter.chapter_id, ChapterContent.chapter_content_text)
            .join(ChapterContent, ChapterContent.chapter_content_id == TranslationJobChapter.source_chapter_content_id)
            .where(
                TranslationJobChapter.job_id == stage.job_id,
                TranslationJobChapter.batch_id == context.task.batch_id,
            )
            .order_by(TranslationJobChapter.chapter_id)
            .execution_options(yield_per=100)
        )
        for chapter_id, content in rows:
            yield ChapterRecord(chapter_id=chapter_id, payload=content)
        return

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
    records = iter_translation_records(fetch_file(context.db, store, previous.output_file_id))
    for record in validate_output_records(records, chapter_ids=chapter_ids, output_types=signature.output_types):
        if isinstance(record, ChapterRecord):
            yield record


callbacks = CeleryActionCallbacks(app, ACTION_CALLBACKS)
_PREPARE_LEASE_SECONDS = 300


@callbacks.new_func(
    expect=TranslationTaskStatus.READY,
    during=TranslationTaskStatus.PREPARING,
    finish=TranslationTaskStatus.PREPARED,
    lease_seconds=_PREPARE_LEASE_SECONDS,
)
def prepare(context: ActionTaskContext) -> None:
    store = get_object_store()
    stage = context.db.execute(
        select(TranslationStage).where(TranslationStage.stage_id == context.task.stage_id)
    ).scalar_one()
    if stage.action != "translate":
        raise ValueError("Translation preparation requires a translate stage")
    config = TranslateConfig.model_validate(stage.config)
    codec = get_codec(config.model)
    chapter_ids = list(
        context.db.scalars(
            select(TranslationJobChapter.chapter_id).where(
                TranslationJobChapter.job_id == stage.job_id,
                TranslationJobChapter.batch_id == context.task.batch_id,
            )
        )
    )
    if not chapter_ids:
        raise ValueError("Cannot prepare an empty translation batch")

    instructions = (
        f"Translate the supplied novel chapter into {config.target_language}. "
        "Preserve its meaning, narrative voice, dialogue, and paragraph structure. "
        "Return only the translated chapter, without commentary or Markdown fences."
    )
    if config.instructions:
        instructions += "\n\n" + config.instructions

    records = validate_output_records(
        _chapter_inputs(context, store, stage, chapter_ids),
        chapter_ids=chapter_ids,
        output_types=ACTIONS["translate"].input_types,
    )
    renew_at = monotonic() + _PREPARE_LEASE_SECONDS / 3
    with TemporaryFile(mode="w+b") as content:
        for record in records:
            if not isinstance(record, ChapterRecord):
                raise ValueError("Translate requires chapter records")
            item = BatchItem(
                key=record.key,
                request=InferenceRequest(
                    model=config.model,
                    messages=(
                        InferenceMessage(role="system", content=instructions),
                        InferenceMessage(role="user", content=record.payload),
                    ),
                    temperature=config.temperature,
                    max_output_tokens=config.max_output_tokens,
                ),
            )
            content.write(codec.encode_request(item))
            if monotonic() >= renew_at:
                context.renew_lease()
                renew_at = monotonic() + _PREPARE_LEASE_SECONDS / 3
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
        context.task.input_file_id = stored_file.file_id
