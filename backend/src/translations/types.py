from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal
from uuid import UUID

type DataName = Literal["chapter", "memories"]
type DataT = frozenset[DataName]
type ActionType = Mapping[str, DataName]
type ActionName = Literal["load_inputs", "prune_memories", "translate"]
type ModelName = Literal["qwen-plus", "qwen-flash", "deepseek/deepseek-v4.1-flash"]


@dataclass(frozen=True)
class TranslationDataKey:
    """Identify one chapter's record of one named stream within a task's stored stage artifact.

    Keys must be unique within the artifact. The owning task supplies job,
    batch, and stage scope. Provider request/chunk identifiers are separate.
    See docs/translations/README.md for the producer/consumer contract.
    """

    chapter_id: UUID
    stream: str


@dataclass(frozen=True)
class ActionSignature:
    inputs: ActionType
    outputs: ActionType
    optional_inputs: ActionType = field(default_factory=dict)
    drops: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.inputs.keys() & self.optional_inputs.keys():
            raise ValueError("A stream cannot be both a required and an optional input")
        if not self.drops <= self.inputs.keys() | self.optional_inputs.keys():
            raise ValueError("Dropped streams must be declared inputs")
        if self.drops & self.outputs.keys():
            raise ValueError("A stream cannot be both dropped and output")

    # Name-set views used by the pairwise pipeline check until actions resolve inputs by stream.
    @property
    def input_types(self) -> DataT:
        return frozenset(self.inputs.values())

    @property
    def output_types(self) -> DataT:
        return frozenset(self.outputs.values())


def infer_type(input_type: ActionType, signature: ActionSignature) -> ActionType:
    for name, expected in signature.inputs.items():
        if name not in input_type:
            raise ValueError(f"requires {name}")
        if input_type[name] != expected:
            raise ValueError(f"{name} must be {expected}, not {input_type[name]}")
    for name, expected in signature.optional_inputs.items():
        if name in input_type and input_type[name] != expected:
            raise ValueError(f"{name} must be {expected}, not {input_type[name]}")
    kept = {name: data_name for name, data_name in input_type.items() if name not in signature.drops}
    return {**kept, **signature.outputs}


def infer_pipeline(initial: ActionType, signatures: Sequence[ActionSignature]) -> list[ActionType]:
    available = initial
    inferred: list[ActionType] = []
    for stage_num, signature in enumerate(signatures):
        try:
            available = infer_type(available, signature)
        except ValueError as error:
            raise ValueError(f"stage {stage_num} {error}") from error
        inferred.append(available)
    return inferred


class TranslationTaskStatus(StrEnum):
    WAITING = "waiting"
    READY = "ready"
    PREPARING = "preparing"
    PREPARED = "prepared"
    SUBMITTING = "submitting"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FINALIZING = "finalizing"
    COMPLETE = "complete"
