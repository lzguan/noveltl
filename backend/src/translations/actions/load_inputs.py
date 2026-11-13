from src.files.dependencies import get_object_store
from src.translations.actions.actions import ActionTaskContext
from src.translations.actions.celery_actions import CeleryActionCallbacks
from src.translations.actions.common.files import store_lines
from src.translations.actions.common.inputs import iter_initial_records, job_config, stage_types
from src.translations.actions.common.outputs import output_records
from src.translations.actions.registry import ACTION_CALLBACKS
from src.translations.celery_app import app
from src.translations.jsonl import encode_translation_record
from src.translations.models import TranslationStage
from src.translations.task_names import LOAD_INPUTS_LOAD
from src.translations.types import TranslationTaskStatus

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
    store = get_object_store()
    loaded = iter_initial_records(context, stage, job_config(context.db, stage.job_id).inputs)
    output = output_records(context, store, stage, loaded, stage_types(context.db, stage))
    context.task.output_file_id = store_lines(
        context, store, map(encode_translation_record, output), renew_seconds=_LEASE_SECONDS / 3
    )
