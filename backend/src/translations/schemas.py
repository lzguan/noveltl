import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Any, ClassVar, Literal, Self

from pydantic import ConfigDict, Field, TypeAdapter, model_validator

from src.memory.types import MemoryType, PluginName
from src.schemas import Model
from src.translations.types import (
    ActionName,
    ActionSignature,
    ModelName,
    StreamType,
    TranslationTaskStatus,
    infer_pipeline,
)
from src.translations.ui import UIHints

MAX_STAGES = 5


class TranslationActionMetadata(Model):
    name: str
    label: str
    config_schema: dict[str, Any]


class TranslationActionsRead(Model):
    actions: list[TranslationActionMetadata]


class PruneMemoriesConfig(Model):
    model_config = ConfigDict(extra="forbid")

    model: ModelName = Field(title="Model", json_schema_extra=UIHints(control="select").schema_extra())
    instructions: str = Field(
        default="",
        title="Instructions",
        json_schema_extra=UIHints(control="textarea", show_after="model").schema_extra(),
    )
    temperature: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
        title="Temperature",
        description="Leave blank to use the provider default.",
        json_schema_extra=UIHints(control="number", show_after="model", placeholder="Provider default").schema_extra(),
    )
    max_output_tokens: int | None = Field(
        default=None,
        gt=0,
        title="Max output tokens",
        description="Leave blank to use the provider default.",
        json_schema_extra=UIHints(control="number", show_after="model", placeholder="Provider default").schema_extra(),
    )

    SIGNATURE: ClassVar[ActionSignature] = ActionSignature(
        inputs={"chapter": "chapter", "memories": "memories"},
        outputs={"memories": "memories"},
    )

    def signature(self) -> ActionSignature:
        return self.SIGNATURE


class PruneMemoriesStageCreate(Model):
    action: Literal["prune_memories"]
    config: PruneMemoriesConfig


class TranslateConfig(Model):
    model_config = ConfigDict(extra="forbid")

    model: ModelName = Field(title="Model", json_schema_extra=UIHints(control="select").schema_extra())
    target_language: str = Field(
        default="English",
        min_length=1,
        title="Target language",
        json_schema_extra=UIHints(control="text", show_after="model").schema_extra(),
    )
    instructions: str = Field(
        default="",
        title="Instructions",
        json_schema_extra=UIHints(control="textarea", show_after="model").schema_extra(),
    )
    temperature: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
        title="Temperature",
        description="Leave blank to use the provider default.",
        json_schema_extra=UIHints(control="number", show_after="model", placeholder="Provider default").schema_extra(),
    )
    max_output_tokens: int | None = Field(
        default=None,
        gt=0,
        title="Max output tokens",
        description="Leave blank to use the provider default.",
        json_schema_extra=UIHints(control="number", show_after="model", placeholder="Provider default").schema_extra(),
    )

    SIGNATURE: ClassVar[ActionSignature] = ActionSignature(
        inputs={"chapter": "chapter"},
        optional_inputs={"memories": "memories"},
        outputs={"chapter": "chapter"},
    )

    def signature(self) -> ActionSignature:
        return self.SIGNATURE


class TranslateStageCreate(Model):
    action: Literal["translate"]
    config: TranslateConfig


type TranslationStageCreate = Annotated[
    PruneMemoriesStageCreate | TranslateStageCreate,
    Field(discriminator="action"),
]


class MemoriesInput(Model):
    model_config = ConfigDict(extra="forbid")

    type: Literal["memories"]
    memory_group_id: uuid.UUID
    plugin_names: list[PluginName] | None = None
    memory_types: list[MemoryType] | None = None
    exclude_current_chapter: bool = True


type TranslationInput = MemoriesInput


class LoadInputsConfig(Model):
    model_config = ConfigDict(extra="forbid")

    inputs: dict[str, TranslationInput] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_inputs(self) -> Self:
        # Stages bind streams by name, and each stream is named after its type for now.
        for name, source in self.inputs.items():
            if name != source.type:
                raise ValueError(f"Input stream {name!r} must be named {source.type!r}")
        return self

    def signature(self) -> ActionSignature:
        outputs: dict[str, StreamType] = {"chapter": "chapter"}
        outputs.update({name: source.type for name, source in self.inputs.items()})
        return ActionSignature(inputs={}, outputs=outputs)


type StageConfig = LoadInputsConfig | PruneMemoriesConfig | TranslateConfig

_action_name = TypeAdapter(ActionName)


def stage_config(action: str, config: Mapping[str, Any]) -> StageConfig:
    match _action_name.validate_python(action):
        case "load_inputs":
            return LoadInputsConfig.model_validate(config)
        case "prune_memories":
            return PruneMemoriesConfig.model_validate(config)
        case "translate":
            return TranslateConfig.model_validate(config)


class TranslationJobConfig(Model):
    start_chapter_num: int | None = Field(default=None, ge=0)
    end_chapter_num: int | None = Field(default=None, ge=0)
    batch_size: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_chapter_range(self) -> Self:
        if (
            self.start_chapter_num is not None
            and self.end_chapter_num is not None
            and self.start_chapter_num >= self.end_chapter_num
        ):
            raise ValueError("start_chapter_num must be less than end_chapter_num")
        return self


class TranslationStageRequest(Model):
    action: str
    config: dict[str, Any] = Field(default_factory=dict)


# A creation request that may still have no stages; the pipeline builder checks these as it goes.
class TranslationJobDraft(Model):
    novel_id: uuid.UUID
    config: TranslationJobConfig
    inputs: dict[str, TranslationInput] = Field(default_factory=dict)
    stages: list[TranslationStageRequest] = Field(default_factory=list, max_length=MAX_STAGES)

    @model_validator(mode="after")
    def validate_inputs(self) -> Self:
        LoadInputsConfig(inputs=self.inputs)
        return self


class TranslationJobCreateRequest(TranslationJobDraft):
    """Public envelope; action-specific validation happens before job creation."""

    stages: list[TranslationStageRequest] = Field(min_length=1, max_length=MAX_STAGES)


class TranslationJobCreate(Model):
    """Validated internal request used by job creation and persistence."""

    novel_id: uuid.UUID
    config: TranslationJobConfig
    inputs: dict[str, TranslationInput] = Field(default_factory=dict)
    stages: list[TranslationStageCreate] = Field(min_length=1, max_length=MAX_STAGES)

    def loader_config(self) -> LoadInputsConfig:
        return LoadInputsConfig(inputs=self.inputs)

    @model_validator(mode="after")
    def validate_pipeline(self) -> Self:
        # Stage numbers match the stored pipeline, where the loader is stage 0.
        infer_pipeline([self.loader_config().signature(), *(stage.config.signature() for stage in self.stages)])
        return self


class TranslationJobStart(Model):
    job_id: uuid.UUID


class TranslationJobCreated(Model):
    job_id: uuid.UUID


class TranslationControlResult(Model):
    affected_batch_ids: list[uuid.UUID] = Field(default_factory=list)
    dispatched_task_ids: list[uuid.UUID] = Field(default_factory=list)
    dispatch_failed_task_ids: list[uuid.UUID] = Field(default_factory=list)


class TranslationTaskRead(Model):
    model_config = ConfigDict(from_attributes=True)
    task_id: uuid.UUID
    stage_id: uuid.UUID
    batch_id: uuid.UUID
    status: TranslationTaskStatus
    failed_at: datetime | None
    error: str | None
    claim_expires_at: datetime | None
    request_file_id: uuid.UUID | None
    output_file_id: uuid.UUID | None


class TranslationStageRead(Model):
    model_config = ConfigDict(from_attributes=True)
    stage_id: uuid.UUID
    stage_num: int
    action: str
    config: dict[str, Any]


class TranslationBatchRead(Model):
    model_config = ConfigDict(from_attributes=True)
    batch_id: uuid.UUID
    batch_num: int


class TranslationJobRead(Model):
    job_id: uuid.UUID
    novel_id: uuid.UUID
    config: dict[str, Any]
    stages: list[TranslationStageRead]
    batches: list[TranslationBatchRead]
    tasks: list[TranslationTaskRead]


class TranslationProgress(Model):
    total_tasks: int = 0
    completed_tasks: int = 0
    total_batches: int = 0
    completed_batches: int = 0
    failed_batches: int = 0
    cancelled_batches: int = 0
    active_batches: int = 0
    startable_batches: int = 0
    resumable_batches: int = 0
    retryable_batches: int = 0


class TranslationJobSummary(Model):
    job_id: uuid.UUID
    config: dict[str, Any]
    stages: list[TranslationStageRead]
    progress: TranslationProgress


class TranslationJobPage(Model):
    items: list[TranslationJobSummary]
    total: int


class TranslationBatchDetail(TranslationBatchRead):
    tasks: list[TranslationTaskRead]


class TranslationBatchPage(Model):
    job: TranslationJobSummary
    items: list[TranslationBatchDetail]
    total: int
    observed_at: datetime
