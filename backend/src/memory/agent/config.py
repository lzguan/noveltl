"""Persisted memory-job configuration and its compatibility interface."""

from typing import Annotated, Any, Literal, Self

from pydantic import ConfigDict, Field, TypeAdapter, model_validator

from src.memory.agent.types import ModelName, ParsedToolsets
from src.schemas import Model


class RecordMemoriesConfig(Model):
    model_config = ConfigDict(extra="forbid")

    model_name: ModelName
    toolsets: dict[str, dict[str, Any]]

    def parse_toolsets(self) -> ParsedToolsets:
        return ParsedToolsets.model_validate(self.toolsets)

    @model_validator(mode="after")
    def validate_toolsets(self) -> Self:
        self.parse_toolsets()
        return self


class TranslateTermsConfig(Model):
    model_config = ConfigDict(extra="forbid")

    model_name: ModelName
    # Defaults off so jobs stored before conventions existed keep their behavior.
    include_conventions: bool = False


class RecordMemoriesStageConfig(RecordMemoriesConfig):
    stage_name: Literal["record_memories"] = "record_memories"


class TranslateTermsStageConfig(TranslateTermsConfig):
    stage_name: Literal["translate_terms"] = "translate_terms"


type StageConfig = Annotated[RecordMemoriesStageConfig | TranslateTermsStageConfig, Field(discriminator="stage_name")]


class JobParamsV1(RecordMemoriesConfig):
    version: Literal[1] = 1

    @property
    def record_memories(self) -> RecordMemoriesConfig:
        return RecordMemoriesConfig(model_name=self.model_name, toolsets=self.toolsets)

    @property
    def translate_terms(self) -> None:
        return None


class JobParamsV2(Model):
    model_config = ConfigDict(extra="forbid")

    version: Literal[2] = 2
    record_memories: RecordMemoriesConfig | None = None
    translate_terms: TranslateTermsConfig | None = None

    @model_validator(mode="after")
    def require_stage(self) -> Self:
        if self.record_memories is None and self.translate_terms is None:
            raise ValueError("Configure at least one memory-job stage")
        return self


type JobParams = Annotated[JobParamsV1 | JobParamsV2, Field(discriminator="version")]
job_params_adapter = TypeAdapter(JobParams)


def resolve_stages(params: JobParams) -> list[StageConfig]:
    """Adapt persisted versions into the ordered inputs consumed by task code."""
    stages: list[StageConfig] = []
    recording = params.record_memories
    if recording is not None:
        stages.append(RecordMemoriesStageConfig.model_validate(recording.model_dump()))
    naming = params.translate_terms
    if naming is not None:
        stages.append(TranslateTermsStageConfig.model_validate(naming.model_dump()))
    return stages
