"""Action metadata for the translation pipeline builder."""

from pydantic import TypeAdapter

from src.translations.schemas import (
    PruneMemoriesConfig,
    TranslateConfig,
    TranslationActionMetadata,
    TranslationActionsRead,
)

_ACTIONS = {
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
