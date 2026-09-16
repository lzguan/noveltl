"""Shared callbacks for plain translation and translation with memories."""

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
from src.memory.models import MemoryGroup
from src.novels.models import ChapterContent
from src.translations.actions.actions import ActionTaskContext
from src.translations.actions.celery_actions import CeleryActionCallbacks
from src.translations.actions.common.memory_inputs import iter_batch_memories
from src.translations.actions.common.prompts import format_memories
from src.translations.actions.registry import ACTION_CALLBACKS
from src.translations.celery_app import app
from src.translations.clients.batch_jobs import (
    BatchJobComplete,
    BatchJobFailed,
    BatchJobId,
    BatchJobPending,
    BatchOutputId,
)
from src.translations.clients.registry import get_batch_client
from src.translations.codecs.batch_lines import BatchItem, BatchItemFailure, InferenceMessage, InferenceRequest
from src.translations.codecs.registry import get_codec
from src.translations.jsonl import encode_translation_record, iter_jsonl_lines, iter_translation_records
from src.translations.models import TranslationJob, TranslationJobChapter, TranslationStage, TranslationTask
from src.translations.records import ChapterRecord, MemoriesRecord, TranslationRecord
from src.translations.schemas import TranslateConfig, TranslateWithMemoriesConfig
from src.translations.types import ACTIONS, ActionName, TranslationTaskStatus
from src.translations.validation import validate_output_records


def _inputs(
    context: ActionTaskContext,
    store: ObjectStore,
    stage: TranslationStage,
    chapter_ids: list[UUID],
    config: TranslateConfig,
) -> Iterator[TranslationRecord]:
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
        if isinstance(config, TranslateWithMemoriesConfig):
            if config.memory_group_id is None:
                raise ValueError("First-stage translate_with_memories requires memory_group_id")
            group = context.db.scalar(
                select(MemoryGroup.memory_group_id)
                .join(TranslationJob, TranslationJob.novel_id == MemoryGroup.novel_id)
                .where(TranslationJob.job_id == stage.job_id, MemoryGroup.memory_group_id == config.memory_group_id)
            )
            if group is None:
                raise ValueError("Memory group does not belong to the translation job's novel")
            yield from iter_batch_memories(
                context.db,
                job_id=stage.job_id,
                batch_id=context.task.batch_id,
                memory_group_id=config.memory_group_id,
                plugin_names=config.plugin_names,
                memory_types=config.memory_types,
                exclude_current_chapter=config.exclude_current_chapter,
            )
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
        if isinstance(record, ChapterRecord) or isinstance(config, TranslateWithMemoriesConfig):
            yield record


def _config(stage: TranslationStage) -> TranslateConfig:
    if stage.action == "translate":
        return TranslateConfig.model_validate(stage.config)
    if stage.action == "translate_with_memories":
        return TranslateWithMemoriesConfig.model_validate(stage.config)
    raise ValueError("Translation callbacks require a translation stage")


def _prompt_inputs(records: Iterator[TranslationRecord], *, with_memories: bool) -> Iterator[tuple[ChapterRecord, str]]:
    chapters: dict[UUID, ChapterRecord] = {}
    memories: dict[UUID, MemoriesRecord] = {}
    for record in records:
        if not with_memories:
            if not isinstance(record, ChapterRecord):
                raise ValueError("Translate requires chapter records")
            yield record, record.payload
            continue
        if isinstance(record, ChapterRecord):
            chapters[record.chapter_id] = record
        else:
            memories[record.chapter_id] = record
        if record.chapter_id in chapters and record.chapter_id in memories:
            chapter = chapters.pop(record.chapter_id)
            memory = memories.pop(record.chapter_id)
            yield (
                chapter,
                f"Context memories:\n{format_memories(memory.payload)}\n\nChapter to translate:\n{chapter.payload}",
            )
    if chapters or memories:
        raise ValueError("Unmatched chapter and memory inputs")


callbacks = CeleryActionCallbacks(app, ACTION_CALLBACKS)
_PREPARE_LEASE_SECONDS = 300
_SUBMIT_LEASE_SECONDS = 300
_FINALIZE_LEASE_SECONDS = 300


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
    config = _config(stage)
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
    if isinstance(config, TranslateWithMemoriesConfig):
        instructions += (
            " Use the context memories for consistent names and continuity; translate only the supplied chapter."
        )
    if config.instructions:
        instructions += "\n\n" + config.instructions

    records = validate_output_records(
        _inputs(context, store, stage, chapter_ids, config),
        chapter_ids=chapter_ids,
        output_types=ACTIONS[TypeAdapter(ActionName).validate_python(stage.action)].input_types,
    )
    renew_at = monotonic() + _PREPARE_LEASE_SECONDS / 3
    with TemporaryFile(mode="w+b") as content:
        for record, prompt in _prompt_inputs(records, with_memories=isinstance(config, TranslateWithMemoriesConfig)):
            item = BatchItem(
                key=record.key,
                request=InferenceRequest(
                    model=config.model,
                    messages=(
                        InferenceMessage(role="system", content=instructions),
                        InferenceMessage(role="user", content=prompt),
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


@callbacks.new_func(
    expect=TranslationTaskStatus.PREPARED,
    during=TranslationTaskStatus.SUBMITTING,
    finish=TranslationTaskStatus.PROCESSING,
    lease_seconds=_SUBMIT_LEASE_SECONDS,
)
def submit(context: ActionTaskContext) -> None:
    if context.task.provider_batch_id is not None:
        return
    if context.task.input_file_id is None:
        raise ValueError("Submission requires a prepared input file")
    stage = context.db.get(TranslationStage, context.task.stage_id)
    if stage is None:
        raise ValueError("Translation stage does not exist")
    config = _config(stage)
    client = get_batch_client(config.model)
    store = get_object_store()
    input_file_id = context.task.input_file_id

    def content() -> Iterator[bytes]:
        renew_at = monotonic() + _SUBMIT_LEASE_SECONDS / 3
        for chunk in fetch_file(context.db, store, input_file_id):
            if monotonic() >= renew_at:
                context.renew_lease()
                renew_at = monotonic() + _SUBMIT_LEASE_SECONDS / 3
            yield chunk

    context.renew_lease()
    job_id = client.create_batch_job(content())
    if not job_id:
        raise ValueError("Batch client returned an empty job ID")
    context.task.provider_batch_id = job_id


@callbacks.new_poll(
    expect=TranslationTaskStatus.PROCESSING,
    during=TranslationTaskStatus.PROCESSING,
    finish=TranslationTaskStatus.PROCESSED,
    interval_seconds=60,
)
def poll(context: ActionTaskContext) -> bool:
    if context.task.provider_batch_id is None:
        raise ValueError("Polling requires a provider batch ID")
    stage = context.db.get(TranslationStage, context.task.stage_id)
    if stage is None:
        raise ValueError("Translation stage does not exist")
    config = _config(stage)
    result = get_batch_client(config.model).poll_batch_job(BatchJobId(context.task.provider_batch_id))
    match result:
        case BatchJobPending():
            return False
        case BatchJobComplete(output_id=output_id):
            if not output_id:
                raise ValueError("Batch client returned an empty output ID")
            context.task.provider_output_id = output_id
            return True
        case BatchJobFailed(error=error):
            raise RuntimeError(f"Provider batch failed: {error}")


@callbacks.new_func(
    expect=TranslationTaskStatus.PROCESSED,
    during=TranslationTaskStatus.FINALIZING,
    finish=TranslationTaskStatus.COMPLETE,
    lease_seconds=_FINALIZE_LEASE_SECONDS,
)
def finalize(context: ActionTaskContext) -> None:
    if context.task.provider_output_id is None:
        raise ValueError("Finalization requires a provider output ID")
    stage = context.db.get(TranslationStage, context.task.stage_id)
    if stage is None:
        raise ValueError("Translation stage does not exist")
    config = _config(stage)
    codec = get_codec(config.model)
    client = get_batch_client(config.model)
    store = get_object_store()
    chapter_ids = list(
        context.db.scalars(
            select(TranslationJobChapter.chapter_id).where(
                TranslationJobChapter.job_id == stage.job_id,
                TranslationJobChapter.batch_id == context.task.batch_id,
            )
        )
    )
    if not chapter_ids:
        raise ValueError("Cannot finalize an empty translation batch")
    output_id = BatchOutputId(context.task.provider_output_id)

    def chunks() -> Iterator[bytes]:
        renew_at = monotonic() + _FINALIZE_LEASE_SECONDS / 3
        for chunk in client.fetch_batch_output(output_id):
            if monotonic() >= renew_at:
                context.renew_lease()
                renew_at = monotonic() + _FINALIZE_LEASE_SECONDS / 3
            yield chunk

    def records() -> Iterator[ChapterRecord]:
        for line in iter_jsonl_lines(chunks()):
            result = codec.decode_result(line)
            if isinstance(result, BatchItemFailure):
                raise ValueError(f"Translation result failed for {result.key}: {result.error}")
            if result.key.data_name != "chapter":
                raise ValueError("Translate output requires chapter keys")
            yield ChapterRecord(chapter_id=result.key.chapter_id, payload=result.text)

    validated = validate_output_records(
        records(),
        chapter_ids=chapter_ids,
        output_types=ACTIONS["translate"].output_types,
    )
    with TemporaryFile(mode="w+b") as content:
        for record in validated:
            content.write(encode_translation_record(record))
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
