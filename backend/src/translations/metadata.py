"""Action metadata for the translation pipeline builder."""

from pydantic import TypeAdapter

from src.translations.schemas import (
    CombineChapterStageCreate,
    PruneMemoriesStageCreate,
    TranslateStageCreate,
    TranslateWithMemoriesStageCreate,
    TranslationActionMetadata,
    TranslationActionsRead,
)
from src.translations.types import ACTIONS, ActionName

_STAGE_TYPES = {
    "translate": TranslateStageCreate,
    "translate_with_memories": TranslateWithMemoriesStageCreate,
    "prune_memories": PruneMemoriesStageCreate,
    "combine_chapter": CombineChapterStageCreate,
}
_LABELS: dict[ActionName, str] = {
    "translate": "Translate",
    "translate_with_memories": "Translate with memories",
    "prune_memories": "Prune memories",
    "combine_chapter": "Combine chapter",
}


def read_action_metadata() -> TranslationActionsRead:
    return TranslationActionsRead(
        actions=[
            TranslationActionMetadata(
                name=name,
                label=_LABELS[name],
                input_types=sorted(signature.input_types),
                output_types=sorted(signature.output_types),
                allowed_as_first_stage=name != "combine_chapter",
                config_schema=TypeAdapter(_STAGE_TYPES[name].model_fields["config"].annotation).json_schema(
                    by_alias=True, mode="validation"
                ),
            )
            for name, signature in ACTIONS.items()
        ]
    )
