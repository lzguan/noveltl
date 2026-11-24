from src.files.dependencies import get_async_object_store
from src.translations.actions.actions import ActionStepSpec, ActionTaskContext, StepSpec, register_steps
from src.translations.actions.common.files import store_lines
from src.translations.actions.common.inputs import iter_initial_records, stage_types
from src.translations.actions.common.outputs import output_records
from src.translations.actions.registry import ACTION_CALLBACKS
from src.translations.actions.taskiq_actions import TaskiqActionCallbacks
from src.translations.broker import broker, schedule_source
from src.translations.jsonl import encode_translation_record
from src.translations.models import TranslationStage
from src.translations.schemas import LoadInputsConfig
from src.translations.task_names import LOAD_INPUTS_LOAD
from src.translations.types import TranslationTaskStatus

_LEASE_SECONDS = 300


async def load(context: ActionTaskContext) -> None:
    stage = await context.db.get(TranslationStage, context.task.stage_id)
    if stage is None or stage.action != "load_inputs":
        raise ValueError("Input loading requires a load_inputs stage")
    store = get_async_object_store()
    loaded = iter_initial_records(context, stage, LoadInputsConfig.model_validate(stage.config).inputs)
    output = output_records(context, store, stage, loaded, await stage_types(context.db, stage))
    context.task.output_file_id = await store_lines(
        context, store, (encode_translation_record(record) async for record in output), renew_seconds=_LEASE_SECONDS / 3
    )


STEPS: tuple[ActionStepSpec, ...] = (
    StepSpec(
        load,
        name=LOAD_INPUTS_LOAD,
        expect=TranslationTaskStatus.READY,
        during=TranslationTaskStatus.FINALIZING,
        finish=TranslationTaskStatus.COMPLETE,
        lease_seconds=_LEASE_SECONDS,
    ),
)

callbacks = TaskiqActionCallbacks(broker, schedule_source, ACTION_CALLBACKS)
register_steps(callbacks, STEPS)
