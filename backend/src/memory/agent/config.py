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


class SummarizeConventionsConfig(Model):
    """Propose translation conventions once per job, anchored on the range's last chapter."""

    model_config = ConfigDict(extra="forbid")

    model_name: ModelName
    # Inclusive start of the chapters whose terms the agent reviews; None means the first chapter.
    since_chapter_num: int | None = Field(default=None, ge=0)


class RecordMemoriesStageConfig(RecordMemoriesConfig):
    stage_name: Literal["record_memories"] = "record_memories"


class SummarizeConventionsStageConfig(SummarizeConventionsConfig):
    stage_name: Literal["summarize_conventions"] = "summarize_conventions"


class TranslateTermsStageConfig(TranslateTermsConfig):
    stage_name: Literal["translate_terms"] = "translate_terms"


type StageConfig = Annotated[
    RecordMemoriesStageConfig | SummarizeConventionsStageConfig | TranslateTermsStageConfig,
    Field(discriminator="stage_name"),
]


class JobParamsV1(RecordMemoriesConfig):
    version: Literal[1] = 1


class JobParamsV2(Model):
    model_config = ConfigDict(extra="forbid")

    version: Literal[2] = 2
    record_memories: RecordMemoriesConfig | None = None
    summarize_conventions: SummarizeConventionsConfig | None = None
    translate_terms: TranslateTermsConfig | None = None

    @model_validator(mode="after")
    def require_stage(self) -> Self:
        if self.record_memories is None and self.summarize_conventions is None and self.translate_terms is None:
            raise ValueError("Configure at least one memory-job stage")
        return self


class JobParamsV3(Model):
    model_config = ConfigDict(extra="forbid")

    version: Literal[3] = 3
    stages: list[StageConfig] = Field(min_length=1)


type JobParams = Annotated[JobParamsV1 | JobParamsV2 | JobParamsV3, Field(discriminator="version")]

job_params_adapter = TypeAdapter(JobParams)


def resolve_stages(params: JobParams) -> list[StageConfig]:
    match params:
        case JobParamsV1():
            return [RecordMemoriesStageConfig(model_name=params.model_name, toolsets=params.toolsets)]
        case JobParamsV2():
            stages: list[StageConfig] = []
            if params.record_memories is not None:
                stages.append(RecordMemoriesStageConfig.model_validate(params.record_memories.model_dump()))
            if params.summarize_conventions is not None:
                stages.append(SummarizeConventionsStageConfig.model_validate(params.summarize_conventions.model_dump()))
            if params.translate_terms is not None:
                stages.append(TranslateTermsStageConfig.model_validate(params.translate_terms.model_dump()))
            return stages
        case JobParamsV3():
            return params.stages


def upgrade_job_params(params: JobParams) -> JobParamsV3:
    return JobParamsV3(stages=resolve_stages(params))


def parse_job_params(raw: object) -> JobParamsV3:
    return upgrade_job_params(job_params_adapter.validate_python(raw))
