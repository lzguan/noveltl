"""
Pydantic schemas for autolabels.
"""

import uuid
from typing import Self

from pydantic import ConfigDict, Field, model_validator

from ..labels.schemas import LabelBase
from ..schemas import Model, SkipDefaultModel
from .constants import MAX_PARAMS_FIELDS, AutoLabelProgress, SepPriority
from .validators import SmallDict


class NERModelParamsBase(SkipDefaultModel):
    """
    Pydantic schema for base NER model parameters. No attributes provided.
    """

    pass


class CluenerModelParams(NERModelParamsBase):
    """
    Pydantic schema for a Cluener model.

    Attributes:
        chunk_size: Integer between 1 and 512. Determines max size of chunks passed to NER model. Has default value 500.
        separators: Dictionary of the form `char : SepPriority`. The predict algorithm will prioritize chunks ending in higher priority separators. Has default value (read the code to see what it is.)
        force_chunk: If no separators found in some interval, force the chunker to chunk mid-sentence. Has default value False.

    Notes:
        To validate this model without injecting default values, call `CluenerModelParams.model_validate(..., context={'skip_default_values' : True})`.
    """

    chunk_size: int = Field(default=500, gt=0, le=512)
    separators: dict[str, SepPriority] = Field(
        default={
            "\n": SepPriority.HIGH,
            "。": SepPriority.MED,
            "！": SepPriority.MED,
            "？": SepPriority.MED,
            ".": SepPriority.MED,
            "!": SepPriority.MED,
            "?": SepPriority.MED,
            "，": SepPriority.LOW,
            "；": SepPriority.LOW,
            "：": SepPriority.LOW,
            ",": SepPriority.LOW,
            ";": SepPriority.LOW,
            ":": SepPriority.LOW,
        }
    )
    force_chunk: bool = False

    @model_validator(mode="after")
    def verify_separators(self) -> Self:
        if not all(len(key) == 1 for key in self.separators):
            raise ValueError("A separator does not have length 1")
        return self


class AutoLabel(Model):
    """
    Pydantic schema for an auto-labeled data entry.

    Attributes:
        auto_label_id: UUID identifier for this AutoLabel.
        auto_label_data: Dictionary containing the auto-labeled data.
        auto_label_model_name: Name of the model used to generate the auto labels.
        auto_label_model_params: Parameters used for the model to generate the auto labels.
        auto_label_status: Labeling progress for this autolabel.
        auto_label_message: Details on status.
        chapter_content_id: UUID of chapter content this AutoLabel is associated with.
        auto_label_last_job_id: Job id of last job that was run on this AutoLabel.
    """

    model_config = ConfigDict(from_attributes=True)
    auto_label_id: uuid.UUID
    auto_label_data: list[LabelBase] | None
    auto_label_model_name: str
    auto_label_model_params: SmallDict = Field(max_length=MAX_PARAMS_FIELDS)
    auto_label_status: AutoLabelProgress
    auto_label_message: str | None = None
    chapter_content_id: uuid.UUID
    auto_label_last_job_id: str


class AutoLabelMeta(Model):
    """
    Pydantic schema for auto-label metadata.

    Attributes:
        auto_label_id: UUID identifier for this AutoLabel.
        auto_label_model_name: Name of the model used to generate the auto labels.
        auto_label_model_params: Parameters used for the model to generate the auto labels.
        auto_label_status: Labeling progress for this autolabel.
        auto_label_message: Details on status.
        chapter_content_id: UUID of chapter content this AutoLabel is associated with.
        auto_label_last_job_id: Job id of last job that was run on this AutoLabel.
    """

    model_config = ConfigDict(from_attributes=True)

    auto_label_id: uuid.UUID
    auto_label_model_name: str
    auto_label_model_params: SmallDict = Field(max_length=MAX_PARAMS_FIELDS)
    auto_label_status: AutoLabelProgress
    auto_label_message: str | None = None
    chapter_content_id: uuid.UUID
    auto_label_last_job_id: str


class CreateAutoLabels(Model):
    """
    Pydantic schema for creating an auto-labeled data entry.

    Attributes:
        novel_id: UUID of novel to create auto labels for.
        auto_label_model_name: Name of the model used to generate the auto labels.
        auto_label_model_params: Parameters used for the model to generate the auto labels.
        chapter_ids: Optional parameter. Restrict to revisions with specific chapter UUIDs.
        start: Optional parameter. Restrict to revisions with chapter num >= start.
        end: Optional parameter. Restrict to revisions with chapter num < end.
        is_public: Optional parameter. Restrict to revisions with this specific public flag.

    """

    novel_id: uuid.UUID
    auto_label_model_name: str
    auto_label_model_params: SmallDict = Field(max_length=MAX_PARAMS_FIELDS)
    chapter_ids: list[uuid.UUID] | None = None
    start: int | None = None
    end: int | None = None
    is_public: bool | None = None

    @model_validator(mode="after")
    def validate_model_params(self) -> Self:
        if self.auto_label_model_name == "cluener":
            resolved_params = CluenerModelParams.model_validate(self.auto_label_model_params)
            self.auto_label_model_params = resolved_params.model_dump()

        # Add 'elif' blocks here for other models (e.g., 'gpt4', 'bert')

        return self
