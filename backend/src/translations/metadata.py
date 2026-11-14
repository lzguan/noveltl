"""Action metadata and advisory type checks for the translation pipeline builder."""

from pydantic import TypeAdapter

from src.translations.pipeline_schemas import (
    TranslationActionCheck,
    TranslationInputPort,
    TranslationLaneEnd,
    TranslationOutputPort,
    TranslationPipelineCheck,
    TranslationStageCheck,
)
from src.translations.schemas import (
    MAX_STAGES,
    LoadInputsConfig,
    PruneMemoriesConfig,
    TranslateConfig,
    TranslationActionMetadata,
    TranslationActionsRead,
    TranslationJobDraft,
)
from src.translations.types import trace_pipeline, trace_stage

_ACTIONS: dict[str, tuple[str, type[PruneMemoriesConfig] | type[TranslateConfig]]] = {
    "translate": ("Translate", TranslateConfig),
    "prune_memories": ("Prune memories", PruneMemoriesConfig),
}


def read_action_metadata() -> TranslationActionsRead:
    return TranslationActionsRead(
        actions=[
            TranslationActionMetadata(
                name=name,
                label=label,
                input_types=sorted(config.SIGNATURE.input_types),
                output_types=sorted(config.SIGNATURE.output_types),
                allowed_as_first_stage=True,
                config_schema=TypeAdapter(config).json_schema(by_alias=True, mode="validation"),
            )
            for name, (label, config) in _ACTIONS.items()
        ]
    )


def check_pipeline(draft: TranslationJobDraft) -> TranslationPipelineCheck:
    # An action fits if some configuration of it type-checks; each config class's SIGNATURE is its
    # least demanding one. The loader is stage 0, and an action this module does not know has no signature.
    actions = ["load_inputs", *(stage.action for stage in draft.stages)]
    signatures = [LoadInputsConfig(inputs=draft.inputs).signature()]
    signatures += [_ACTIONS[action][1].SIGNATURE if action in _ACTIONS else None for action in actions[1:]]
    stages = trace_pipeline(signatures)
    producers = stages[-1].producers
    full = f"a job can have at most {MAX_STAGES} stages" if len(draft.stages) >= MAX_STAGES else None
    return TranslationPipelineCheck(
        stages=[
            TranslationStageCheck(
                action=action,
                inputs=[TranslationInputPort.model_validate(port, from_attributes=True) for port in stage.inputs],
                outputs=[
                    TranslationOutputPort(stream=stream, type=stream_type)
                    for stream, stream_type in stage.outputs.items()
                ],
                warning=stage.warning,
            )
            for action, stage in zip(actions, stages, strict=True)
        ],
        ends=[
            TranslationLaneEnd(stream=stream, type=stream_type, source=source)
            for stream, (source, stream_type) in producers.items()
        ],
        addable=[
            TranslationActionCheck(
                action=action, warning=full or trace_stage(producers, config.SIGNATURE, len(stages)).warning
            )
            for action, (_, config) in _ACTIONS.items()
        ],
    )
