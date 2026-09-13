from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

type DataName = Literal["chapter", "memories"]
type DataT = frozenset[DataName]
type ActionName = Literal["prune_memories", "combine_chapter", "translate_with_memories", "translate"]


@dataclass(frozen=True)
class ActionSignature:
    input_types: DataT
    output_types: DataT


ACTIONS: dict[ActionName, ActionSignature] = {
    "prune_memories": ActionSignature(
        input_types=frozenset(("chapter", "memories")),
        output_types=frozenset(("memories",)),
    ),
    "combine_chapter": ActionSignature(
        input_types=frozenset(("memories",)),
        output_types=frozenset(("chapter", "memories")),
    ),
    "translate_with_memories": ActionSignature(
        input_types=frozenset(("chapter", "memories")),
        output_types=frozenset(("chapter",)),
    ),
    "translate": ActionSignature(
        input_types=frozenset(("chapter",)),
        output_types=frozenset(("chapter",)),
    ),
}


class TranslationTaskStatus(StrEnum):
    WAITING = "waiting"
    READY = "ready"
    PREPARING = "preparing"
    PREPARED = "prepared"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FINALIZING = "finalizing"
    COMPLETE = "complete"
