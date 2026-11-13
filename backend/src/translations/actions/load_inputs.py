from tempfile import TemporaryFile
from time import monotonic

from src.files.access import create_file
from src.files.config import file_store_settings
from src.files.dependencies import get_object_store
from src.translations.actions.actions import ActionTaskContext
from src.translations.actions.celery_actions import CeleryActionCallbacks
from src.translations.actions.common.inputs import batch_chapter_ids, iter_initial_records, job_config, stage_signature
from src.translations.actions.registry import ACTION_CALLBACKS
from src.translations.celery_app import app
from src.translations.jsonl import encode_translation_record
from src.translations.models import TranslationStage
from src.translations.task_names import LOAD_INPUTS_LOAD
from src.translations.types import TranslationTaskStatus
from src.translations.validation import validate_output_records

callbacks = CeleryActionCallbacks(app, ACTION_CALLBACKS)
_LEASE_SECONDS = 300


@callbacks.new_func(
    expect=TranslationTaskStatus.READY,
    during=TranslationTaskStatus.FINALIZING,
    finish=TranslationTaskStatus.COMPLETE,
    lease_seconds=_LEASE_SECONDS,
    name=LOAD_INPUTS_LOAD,
)
def load(context: ActionTaskContext) -> None:
    stage = context.db.get(TranslationStage, context.task.stage_id)
    if stage is None or stage.action != "load_inputs":
        raise ValueError("Input loading requires a load_inputs stage")
    config = job_config(context.db, stage.job_id)
    records = validate_output_records(
        iter_initial_records(context, stage, config.inputs),
        chapter_ids=batch_chapter_ids(context, stage),
        output_type=stage_signature(config, stage).outputs,
    )
    store = get_object_store()
    renew_at = monotonic() + _LEASE_SECONDS / 3
    with TemporaryFile(mode="w+b") as content:
        for record in records:
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
        context.db.flush()
        context.task.output_file_id = stored_file.file_id
