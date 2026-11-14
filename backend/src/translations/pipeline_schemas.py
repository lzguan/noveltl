from src.schemas import Model
from src.translations.types import LinkKind, StreamType


class TranslationOutputPort(Model):
    stream: str
    type: StreamType


class TranslationInputPort(Model):
    stream: str
    type: StreamType
    optional: bool
    drops: bool
    link: LinkKind
    source: int | None
    source_type: StreamType | None


class TranslationStageCheck(Model):
    action: str
    inputs: list[TranslationInputPort]
    outputs: list[TranslationOutputPort]
    warning: str | None


class TranslationLaneEnd(Model):
    stream: str
    type: StreamType
    source: int


class TranslationActionCheck(Model):
    action: str
    warning: str | None


# Advisory feedback for the pipeline builder; job creation remains the authority. `stages[0]` is the
# loader, so a stage's index is its stored stage number and the index other ports name as `source`.
class TranslationPipelineCheck(Model):
    stages: list[TranslationStageCheck]
    ends: list[TranslationLaneEnd]
    addable: list[TranslationActionCheck]
