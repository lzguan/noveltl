"""Translate chapters through provider-neutral batch inference, using memories when the job loads them."""

import json
from collections.abc import Iterator
from time import monotonic

from src.files.access import fetch_file
from src.files.dependencies import get_object_store
from src.translations.actions.actions import ActionTaskContext
from src.translations.actions.celery_actions import CeleryActionCallbacks
from src.translations.actions.common.files import store_lines
from src.translations.actions.common.inputs import (
    group_by_chapter,
    resolve_inputs,
    select_streams,
    stage_types,
)
from src.translations.actions.common.outputs import output_records
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
from src.translations.jsonl import encode_translation_record, iter_jsonl_lines
from src.translations.models import TranslationStage
from src.translations.records import ChapterRecord, ConventionsRecord, MemoriesRecord, TermsRecord
from src.translations.schemas import TranslateConfig
from src.translations.task_names import (
    TRANSLATE_FINALIZE,
    TRANSLATE_POLL,
    TRANSLATE_PREPARE,
    TRANSLATE_SUBMIT,
)
from src.translations.types import TranslationTaskStatus

callbacks = CeleryActionCallbacks(app, ACTION_CALLBACKS)
_PREPARE_LEASE_SECONDS = 300
_SUBMIT_LEASE_SECONDS = 300
_FINALIZE_LEASE_SECONDS = 300


def _stage(context: ActionTaskContext) -> tuple[TranslationStage, TranslateConfig]:
    stage = context.db.get(TranslationStage, context.task.stage_id)
    if stage is None or stage.action != "translate":
        raise ValueError("Translation callbacks require a translate stage")
    return stage, TranslateConfig.model_validate(stage.config)


@callbacks.new_func(
    expect=TranslationTaskStatus.READY,
    during=TranslationTaskStatus.PREPARING,
    finish=TranslationTaskStatus.PREPARED,
    lease_seconds=_PREPARE_LEASE_SECONDS,
    name=TRANSLATE_PREPARE,
)
def prepare(context: ActionTaskContext) -> None:
    stage, config = _stage(context)
    store, codec = get_object_store(), get_codec(config.model)
    instructions = (
        f"Translate the supplied novel chapter into {config.target_language}. "
        "Preserve its meaning, narrative voice, dialogue, and paragraph structure. "
        "Return only the translated chapter, without commentary or Markdown fences."
    )
    memory_instructions = (
        " Use the context memories for consistent names and continuity; translate only the supplied chapter."
    )
    extra_instructions = "\n\n" + config.instructions if config.instructions else ""
    types = stage_types(context.db, stage)
    records = select_streams(resolve_inputs(context, store, stage, types.before), types.declared)

    def requests() -> Iterator[bytes]:
        for inputs in group_by_chapter(records, streams=types.before.keys() & types.declared):
            chapter = inputs["chapter"]
            memories = inputs.get("memories")
            terms = inputs.get("terms")
            conventions = inputs.get("conventions")
            if not isinstance(chapter, ChapterRecord):
                raise ValueError("Translation requires chapter records in the chapter stream")
            system = instructions
            sections: list[str] = []
            if memories is not None:
                if not isinstance(memories, MemoriesRecord):
                    raise ValueError("Translation requires memories records in the memories stream")
                system += memory_instructions
                sections.append(f"Context memories:\n{format_memories(memories.payload)}")
            if terms is not None:
                if not isinstance(terms, TermsRecord):
                    raise ValueError("Translation requires terms records in the terms stream")
                system += (
                    " Use the supplied canonical term translations for exact source forms,"
                    " preserving the source's choice of names and aliases."
                )
                sections.append("Canonical term translations:\n" + json.dumps(terms.payload, ensure_ascii=False))
            if conventions is not None:
                if not isinstance(conventions, ConventionsRecord):
                    raise ValueError("Translation requires conventions records in the conventions stream")
                system += " Follow the supplied naming and style conventions."
                sections.append(
                    "Translation conventions:\n"
                    + json.dumps([rule.model_dump(mode="json") for rule in conventions.payload], ensure_ascii=False)
                )
            prompt = (
                "\n\n".join([*sections, f"Chapter to translate:\n{chapter.payload}"]) if sections else chapter.payload
            )
            item = BatchItem(
                key=chapter.key,
                request=InferenceRequest(
                    model=config.model,
                    messages=(
                        InferenceMessage(role="system", content=system + extra_instructions),
                        InferenceMessage(role="user", content=prompt),
                    ),
                    temperature=config.temperature,
                    max_output_tokens=config.max_output_tokens,
                ),
            )
            yield codec.encode_request(item)

    context.task.request_file_id = store_lines(context, store, requests(), renew_seconds=_PREPARE_LEASE_SECONDS / 3)


@callbacks.new_func(
    expect=TranslationTaskStatus.PREPARED,
    during=TranslationTaskStatus.SUBMITTING,
    finish=TranslationTaskStatus.PROCESSING,
    lease_seconds=_SUBMIT_LEASE_SECONDS,
    name=TRANSLATE_SUBMIT,
)
def submit(context: ActionTaskContext) -> None:
    if context.task.provider_batch_id is not None:
        return
    if context.task.request_file_id is None:
        raise ValueError("Submission requires a prepared request file")
    _, config = _stage(context)
    client = get_batch_client(config.model)
    store = get_object_store()
    request_file_id = context.task.request_file_id

    def content() -> Iterator[bytes]:
        renew_at = monotonic() + _SUBMIT_LEASE_SECONDS / 3
        for chunk in fetch_file(context.db, store, request_file_id):
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
    name=TRANSLATE_POLL,
)
def poll(context: ActionTaskContext) -> bool:
    if context.task.provider_batch_id is None:
        raise ValueError("Polling requires a provider batch ID")
    _, config = _stage(context)
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
    name=TRANSLATE_FINALIZE,
)
def finalize(context: ActionTaskContext) -> None:
    if context.task.provider_output_id is None:
        raise ValueError("Finalization requires a provider output ID")
    stage, config = _stage(context)
    codec = get_codec(config.model)
    client = get_batch_client(config.model)
    store = get_object_store()
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
            yield ChapterRecord(chapter_id=result.key.chapter_id, stream=result.key.stream, payload=result.text)

    output = output_records(context, store, stage, records(), stage_types(context.db, stage))
    context.task.output_file_id = store_lines(
        context, store, map(encode_translation_record, output), renew_seconds=_FINALIZE_LEASE_SECONDS / 3
    )
