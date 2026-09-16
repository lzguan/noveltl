import uuid
from datetime import datetime
from itertools import pairwise
from typing import Annotated, Any, Literal, Self

from pydantic import ConfigDict, Field, model_validator

from src.memory.types import MemoryType, PluginName
from src.schemas import Model
from src.translations.types import ACTIONS, ModelName, TranslationTaskStatus


class TranslationStageCreateBase(Model):
    config: dict[str, Any] = Field(default_factory=dict)


class PruneMemoriesConfig(Model):
    model_config = ConfigDict(extra="forbid")

    model: ModelName
    instructions: str = ""
    temperature: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    max_output_tokens: int | None = Field(default=None, gt=0)
    memory_group_id: uuid.UUID | None = None
    plugin_names: list[PluginName] | None = None
    memory_types: list[MemoryType] | None = None
    exclude_current_chapter: bool = True


class PruneMemoriesStageCreate(Model):
    action: Literal["prune_memories"]
    config: PruneMemoriesConfig


class CombineChapterStageCreate(TranslationStageCreateBase):
    action: Literal["combine_chapter"]


class TranslateConfig(Model):
    model_config = ConfigDict(extra="forbid")

    model: ModelName
    target_language: str = Field(default="English", min_length=1)
    instructions: str = ""
    temperature: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    max_output_tokens: int | None = Field(default=None, gt=0)


class TranslateWithMemoriesConfig(TranslateConfig):
    memory_group_id: uuid.UUID | None = None
    plugin_names: list[PluginName] | None = None
    memory_types: list[MemoryType] | None = None
    exclude_current_chapter: bool = True


class TranslateWithMemoriesStageCreate(Model):
    action: Literal["translate_with_memories"]
    config: TranslateWithMemoriesConfig


class TranslateStageCreate(Model):
    action: Literal["translate"]
    config: TranslateConfig


type TranslationStageCreate = Annotated[
    PruneMemoriesStageCreate | CombineChapterStageCreate | TranslateWithMemoriesStageCreate | TranslateStageCreate,
    Field(discriminator="action"),
]


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


class TranslationJobCreate(Model):
    novel_id: uuid.UUID
    config: TranslationJobConfig
    stages: list[TranslationStageCreate] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def validate_pipeline(self) -> Self:
        first = self.stages[0]
        if (
            isinstance(first, (TranslateWithMemoriesStageCreate, PruneMemoriesStageCreate))
            and first.config.memory_group_id is None
        ):
            raise ValueError(f"First-stage {first.action} requires memory_group_id")
        for stage_num, (current_stage, next_stage) in enumerate(pairwise(self.stages)):
            output_types = ACTIONS[current_stage.action].output_types
            input_types = ACTIONS[next_stage.action].input_types
            missing_types = input_types - output_types
            if missing_types:
                raise ValueError(
                    f"stage {stage_num + 1} requires data not produced by stage {stage_num}: "
                    f"{', '.join(sorted(missing_types))}"
                )

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
    input_file_id: uuid.UUID | None
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
    initial_file_id: uuid.UUID | None


class TranslationJobRead(Model):
    job_id: uuid.UUID
    novel_id: uuid.UUID
    config: dict[str, Any]
    stages: list[TranslationStageRead]
    batches: list[TranslationBatchRead]
    tasks: list[TranslationTaskRead]
