"""Action metadata for the translation pipeline builder."""

from pydantic import TypeAdapter

from src.translations.schemas import (
    PruneMemoriesStageCreate,
    TranslateStageCreate,
    TranslationActionMetadata,
    TranslationActionsRead,
)
from src.translations.types import ACTIONS

_STAGE_TYPES = {
    "translate": TranslateStageCreate,
    "prune_memories": PruneMemoriesStageCreate,
}
_LABELS = {
    "translate": "Translate",
    "prune_memories": "Prune memories",
}


def read_action_metadata() -> TranslationActionsRead:
    return TranslationActionsRead(
        actions=[
            TranslationActionMetadata(
                name=name,
                label=_LABELS[name],
                input_types=sorted(signature({}).input_types),
                output_types=sorted(signature({}).output_types),
                allowed_as_first_stage=True,
                config_schema=TypeAdapter(_STAGE_TYPES[name].model_fields["config"].annotation).json_schema(
                    by_alias=True, mode="validation"
                ),
            )
            for name, signature in ACTIONS.items()
            if name in _STAGE_TYPES
        ]
    )
