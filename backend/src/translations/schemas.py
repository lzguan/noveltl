import uuid
from itertools import pairwise
from typing import Annotated, Any, Literal, Self

from pydantic import Field, model_validator

from src.schemas import Model
from src.translations.types import ACTIONS


class TranslationStageCreateBase(Model):
    config: dict[str, Any] = Field(default_factory=dict)


class PruneMemoriesStageCreate(TranslationStageCreateBase):
    action: Literal["prune_memories"]


class CombineChapterStageCreate(TranslationStageCreateBase):
    action: Literal["combine_chapter"]


class TranslateWithMemoriesStageCreate(TranslationStageCreateBase):
    action: Literal["translate_with_memories"]


class TranslateStageCreate(TranslationStageCreateBase):
    action: Literal["translate"]


type TranslationStageCreate = Annotated[
    PruneMemoriesStageCreate
    | CombineChapterStageCreate
    | TranslateWithMemoriesStageCreate
    | TranslateStageCreate,
    Field(discriminator="action"),
]


class TranslationJobCreate(Model):
    novel_id: uuid.UUID
    start_chapter_num: int | None = Field(default=None, ge=0)
    end_chapter_num: int | None = Field(default=None, ge=0)
    config: dict[str, Any] = Field(default_factory=dict)
    stages: list[TranslationStageCreate] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def validate_job(self) -> Self:
        if (
            self.start_chapter_num is not None
            and self.end_chapter_num is not None
            and self.start_chapter_num >= self.end_chapter_num
        ):
            raise ValueError("start_chapter_num must be less than end_chapter_num")

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
