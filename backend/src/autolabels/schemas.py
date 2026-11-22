"""
Pydantic schemas for autolabels.
"""

import uuid
from datetime import datetime

from pydantic import ConfigDict, Field

from src.autolabels.constants import AutoLabelProgress
from src.autolabels.params import NERParams
from src.labels.schemas import LabelBase
from src.schemas import Model


class AutoLabelRun(Model):
    """
    Pydantic schema for an autolabel run (batch).

    A run groups autolabels created together in a single request.

    Attributes:
        run_id: UUID identifier for this run.
        triggered_by: UUID of user who triggered the run, or None.
        model_name: Name of the NER model used.
        model_params: Parameters for the NER model.
        created_at: When the run was created.
    """

    model_config = ConfigDict(from_attributes=True)
    run_id: uuid.UUID
    novel_id: uuid.UUID
    triggered_by: uuid.UUID
    model_name: str
    model_params: NERParams
    created_at: datetime


class AutoLabel(Model):
    """
    Pydantic schema for a single auto-labeled data entry with its label data.

    Attributes:
        auto_label_id: UUID identifier for this AutoLabel.
        auto_label_data: List of labels produced by the NER model, or None if not yet complete.
        auto_label_status: Labeling progress for this autolabel.
        auto_label_message: Details on status (e.g. failure reason).
        auto_label_last_job_id: Job id of last request to autogenerate.
        chapter_content_id: UUID of chapter content this AutoLabel is for.
        run_id: UUID of the AutoLabelRun this autolabel belongs to.
    """

    model_config = ConfigDict(from_attributes=True)
    auto_label_id: uuid.UUID
    auto_label_data: list[LabelBase] | None = None
    auto_label_status: AutoLabelProgress
    auto_label_message: str | None = None
    auto_label_last_job_id: uuid.UUID | None = None
    chapter_content_id: uuid.UUID
    run_id: uuid.UUID


class AutoLabelMeta(Model):
    """
    Pydantic schema for auto-label metadata (no label data payload).

    Attributes:
        auto_label_id: UUID identifier for this AutoLabel.
        auto_label_status: Labeling progress for this autolabel.
        auto_label_message: Details on status.
        auto_label_last_job_id: Job id of last request to autogenerate.
        chapter_content_id: UUID of chapter content this AutoLabel is for.
        run_id: UUID of the AutoLabelRun this autolabel belongs to.
    """

    model_config = ConfigDict(from_attributes=True)
    auto_label_id: uuid.UUID
    auto_label_status: AutoLabelProgress
    auto_label_message: str | None = None
    auto_label_last_job_id: uuid.UUID | None = None
    chapter_content_id: uuid.UUID
    run_id: uuid.UUID


class AutoLabelMetaWithCid(Model):
    auto_label_meta: AutoLabelMeta
    chapter_id: uuid.UUID


class CreateAutoLabels(Model):
    """
    Pydantic schema for creating a new autolabel run.

    Attributes:
        novel_id: UUID of novel to create auto labels for.
        params: Parameters for the NER model. Discriminated by model_name attribute.
        chapter_ids: Optional. Restrict to specific chapter UUIDs.
        start: Optional. Restrict to chapters with number >= start.
        end: Optional. Restrict to chapters with number < end.
        is_public: Optional. Restrict to chapters with this specific public flag.
    """

    novel_id: uuid.UUID
    params: NERParams = Field(discriminator="model_name")
    chapter_ids: list[uuid.UUID] | None = None
    start: int | None = None
    end: int | None = None
    is_public: bool | None = None


class CreateAutoLabelsResponse(Model):
    """
    Pydantic schema for the response after creating autolabels.

    Attributes:
        run: The autolabel run that was created.
        autolabels: The list of autolabel entries created in this run.
    """

    run: AutoLabelRun
    autolabels: list[AutoLabelMetaWithCid]


class CreateLabelDataByAutoLabel(Model):
    """
    Pydantic schema to specifiy a set of AutoLabels to be moved to LabelDatas.

    Attributes:
        run_id: UUID of the autolabel run whose results should be promoted.
        chapter_ids: Optional filter on what chapters to include.
        start: Optional filter on the least chapter number to include.
        end: Optional filter on the greatest chapter number to include.
    """

    run_id: uuid.UUID
    chapter_ids: list[uuid.UUID] | None = None
    start: int | None = None
    end: int | None = None


class CreateLabelDataByAutoLabelStatus(Model):
    """
    Return message for CreateLabelDataByAutoLabel.

    Attributes:
        success: List of tuples of (chapter_id, chapter_content_id) for successful inserts.
        errors: List of tuples of (chapter_id, chapter_content_id, error message) for failed inserts.
    """

    success: list[tuple[uuid.UUID, uuid.UUID]]
    errors: list[tuple[uuid.UUID, uuid.UUID, str]]
