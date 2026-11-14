from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal
from uuid import UUID

type StreamType = Literal["chapter", "memories"]
type DataT = frozenset[StreamType]
type ActionType = Mapping[str, StreamType]
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


# How an input port is fed: by a producer of the right type, by nothing (required), by a producer of
# another type, or by nothing (optional).
type LinkKind = Literal["linked", "broken", "incompatible", "absent"]
# For each available stream, the stage whose output port holds its current version, and its type.
type Producers = Mapping[str, tuple[int, StreamType]]


@dataclass(frozen=True)
class InputPort:
    stream: str
    type: StreamType
    optional: bool
    drops: bool
    link: LinkKind
    source: int | None
    source_type: StreamType | None


@dataclass(frozen=True)
class StageTrace:
    inputs: tuple[InputPort, ...]
    outputs: ActionType
    warning: str | None
    producers: Producers

    @property
    def available(self) -> ActionType:
        return {stream: stream_type for stream, (_, stream_type) in self.producers.items()}


def _input_ports(producers: Producers, signature: ActionSignature) -> Iterator[InputPort]:
    for declared, optional in ((signature.inputs, False), (signature.optional_inputs, True)):
        for stream, expected in declared.items():
            source, source_type = producers.get(stream, (None, None))
            link: LinkKind
            if source_type is None:
                link = "absent" if optional else "broken"
            else:
                link = "linked" if source_type == expected else "incompatible"
            yield InputPort(stream, expected, optional, stream in signature.drops, link, source, source_type)


def trace_stage(producers: Producers, signature: ActionSignature | None, index: int) -> StageTrace:
    # A stage fits when no input port is broken or incompatible. A fitting stage removes the streams
    # it drops and becomes the producer of the streams it outputs; any other stage, including one
    # with no signature, leaves the producers unchanged.
    if signature is None:
        return StageTrace((), {}, "unknown action", producers)
    ports = tuple(_input_ports(producers, signature))
    problems = [f"requires {port.stream}" for port in ports if port.link == "broken"]
    problems += [
        f"{port.stream} must be {port.type}, not {port.source_type}" for port in ports if port.link == "incompatible"
    ]
    if problems:
        return StageTrace(ports, signature.outputs, "; ".join(problems), producers)
    kept = {stream: producer for stream, producer in producers.items() if stream not in signature.drops}
    written = {stream: (index, stream_type) for stream, stream_type in signature.outputs.items()}
    return StageTrace(ports, signature.outputs, None, {**kept, **written})


def trace_pipeline(signatures: Sequence[ActionSignature | None]) -> list[StageTrace]:
    producers: Producers = {}
    stages: list[StageTrace] = []
    for index, signature in enumerate(signatures):
        stages.append(trace_stage(producers, signature, index))
        producers = stages[-1].producers
    return stages


def infer_pipeline(signatures: Sequence[ActionSignature]) -> list[ActionType]:
    stages = trace_pipeline(signatures)
    for stage_num, stage in enumerate(stages):
        if stage.warning is not None:
            raise ValueError(f"stage {stage_num} {stage.warning}")
    return [stage.available for stage in stages]


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
