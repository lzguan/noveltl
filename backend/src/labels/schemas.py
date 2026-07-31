"""
Pydantic schemas for labels.
"""

import uuid
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, TypeAdapter, model_validator

from src.labels.constants import (
    MAX_LABEL_ENTITY_GROUP_NAME_LEN,
    MAX_LABEL_GROUP_NAME_LEN,
    MAX_LABEL_WORD_LEN,
    LabelRole,
)
from src.schemas import Model


class LabelGroup(Model):
    """
    Pydantic schema for a label group.

    Attributes:
        label_group_id: UUID identifier for this label group.
        label_group_name: Name of this label group.
        novel_id: UUID of novel this label group belongs to.
    """

    model_config = ConfigDict(from_attributes=True)

    label_group_id: uuid.UUID
    label_group_name: str = Field(max_length=MAX_LABEL_GROUP_NAME_LEN)
    novel_id: uuid.UUID


class LabelGroupWithRole(Model):
    """
    Pydantic schema for a label group with a user's role in that label group.

    Attributes:
        label_group: LabelGroup object.
        role: Role of the user in this label group.
    """

    label_group: LabelGroup
    role: LabelRole


class CreateLabelGroup(Model):
    """
    Pydantic schema for validating forms for creating a label group.

    Attributes:
        label_group_name: Name of label group to create.
        novel_id: UUID of novel this label group belongs to.
    """

    label_group_name: str = Field(max_length=MAX_LABEL_GROUP_NAME_LEN)
    novel_id: uuid.UUID


class UpdateLabelGroup(Model):
    """
    Pydantic schema for validating forms for updating a label group.

    Attributes:
        label_group_name: New name of label group.
    """

    label_group_name: str = Field(max_length=MAX_LABEL_GROUP_NAME_LEN)


class LabelData(Model):
    """
    Pydantic schema for a list of labels in some text.

    Attributes:
        label_data_id: UUID identifier for this LabelData.
        label_group_id: UUID of label group this LabelData belongs to.
        chapter_content_id: UUID of chapter content this LabelData is labelling.
    """

    model_config = ConfigDict(from_attributes=True)
    label_data_id: uuid.UUID

    label_group_id: uuid.UUID
    chapter_content_id: uuid.UUID


class LabelBase(Model):
    """
    Pydantic schema for a single label without a parent LabelData reference.
    Used by autolabels and other contexts where labels exist independently of a LabelData.

    Attributes:
        label_entity_group: Some arbitrary string denoting the entity group this label belongs to (e.g. PERSON, LOCATION, etc.).
        label_score: Some float corresponding to how likely a label is to be correct. Used by label autogeneration modules (TBD).
        label_word: Word that this label is labeling.
        label_start: Start position of this label in text.
        label_end: End position of this label in text.
        label_dirty: Use TBD, most likely will be for score calculations in LabelData aggregate operations.

    Note:
        label_start must be strictly less than label_end. Otherwise a ValueError will occur.
        label_word must have length label_end - label_start. Otherwise a ValueError will occur.
    """

    model_config = ConfigDict(from_attributes=True)
    label_entity_group: str | None = Field(max_length=MAX_LABEL_ENTITY_GROUP_NAME_LEN)
    label_score: float = Field(ge=0.0, le=1.0)
    label_word: str = Field(max_length=MAX_LABEL_WORD_LEN)
    label_start: int = Field(ge=0)
    label_end: int = Field(ge=0)
    label_dirty: bool

    @model_validator(mode="after")
    def check_start_lt_end(self) -> Self:
        if self.label_start >= self.label_end:
            raise ValueError("Label start must be less than label end")
        return self

    @model_validator(mode="after")
    def check_word_len(self) -> Self:
        if len(self.label_word) != self.label_end - self.label_start:
            raise ValueError("Length of label word does not match label bounds")
        return self

    def __repr__(self) -> str:
        return f"{{label_word : {self.label_word},label_entity_group : {self.label_entity_group},label_start : {self.label_start},label_end : {self.label_end},label_score : {self.label_score},label_entity_group : {self.label_entity_group}}}"


class Label(LabelBase):
    """
    Pydantic schema for a label that belongs to a LabelData.
    Extends LabelBase with a label_data_id foreign key and label_id pkey.
    """

    label_data_id: uuid.UUID
    label_id: uuid.UUID


class CreateLabelData(Model):
    """
    Pydantic schema for validating create requests for label data.

    Attributes:
        chapter_content_id: UUID of chapter content being labelled.
    """

    chapter_content_id: uuid.UUID


class AddLabelOp(Model):
    """
    Pydantic schema for a label add operation. Adds a new label to the label data with the given parameters.

    Attributes:
        op: The string literal 'add'.
        dirty: Boolean whether to mark the label as dirty.
        entity_group: Optional entity group assigned to the label.
        score: Float score between 0.0 and 1.0 representing how likely this label is to be an entity.
        start_pos: Inclusive start position in the chapter text.
        end_pos: Exclusive end position in the chapter text.
    """

    op: Literal["add"]
    dirty: bool = True
    entity_group: str | None = Field(default=None, max_length=MAX_LABEL_ENTITY_GROUP_NAME_LEN)
    score: float = Field(default=1.0, ge=0.0, le=1.0)
    start_pos: int = Field(ge=0)
    end_pos: int = Field(ge=0)

    @model_validator(mode="after")
    def check_start_lt_end(self) -> Self:
        if self.start_pos >= self.end_pos:
            raise ValueError("Start pos must be less than end pos")
        return self

    @model_validator(mode="after")
    def check_length(self) -> Self:
        if self.end_pos - self.start_pos > MAX_LABEL_WORD_LEN:
            raise ValueError(f"Label length must be less than or equal to {MAX_LABEL_WORD_LEN}")
        return self


class DeleteLabelOp(Model):
    """
    Pydantic schema for a label delete operation. Deletes the label with label_id.

    Attributes:
        op: The string literal 'delete'.
        label_id: ID of the label to delete.
    """

    op: Literal["delete"]
    label_id: uuid.UUID


class UpdateLabelOp(Model):
    """
    Pydantic schema for a label update operation. Partial updates performed on label with label_id.

    Attributes:
        op: The string literal 'update'.
        label_id: ID of the label to update.
        start_pos: Optional parameter. The new start position of the label.
        end_pos: Optional parameter. The new end position of the label.
        dirty: Optional parameter. Value to change the current label's dirty value to.
        entity_group: Optional parameter. New entity group for this label.
        score: Optional parameter. New score for the entity.
    """

    op: Literal["update"]
    start_pos: int | None = Field(default=None, ge=0)
    end_pos: int | None = Field(default=None, ge=0)
    dirty: bool | None = None
    entity_group: str | None = Field(default=None, max_length=MAX_LABEL_ENTITY_GROUP_NAME_LEN)
    score: float | None = Field(default=None, ge=0, le=1)
    label_id: uuid.UUID

    @model_validator(mode="after")
    def check_start_lt_end(self) -> Self:
        if self.start_pos is not None and self.end_pos is not None:
            if self.start_pos >= self.end_pos:
                raise ValueError("Start pos must be less than end pos")
        return self

    # need to perform length validation at runtime


type LabelOp = Annotated[AddLabelOp | DeleteLabelOp | UpdateLabelOp, Field(discriminator="op")]
label_op_adapter = TypeAdapter[LabelOp](LabelOp)

type OpResult = Annotated[uuid.UUID, Field()]


class OpsResult(Model):
    """
    Pydantic schema for a list of label operation results.

    Attributes:
        results: A list of UUIDs corresponding to the results of each label operation.
    """

    results: list[OpResult]


class UpdateLabelDataStream(Model):
    """
    Pydantic schema for an atomic stream of label operations.

    Attributes:
        ops: A list of label operations.
    """

    ops: list[LabelOp]


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


class LabelContributor(Model):
    """
    Pydantic schema for a label contributor, which can be either a user or an autolabel model.

    Attributes:
        label_contributor_role: Role of the contributor, either a user or an autolabel model.
        label_group_id: UUID of label group this contributor belongs to.
        user_id: UUID of user
    """

    model_config = ConfigDict(from_attributes=True)
    label_contributor_role: LabelRole
    label_group_id: uuid.UUID
    user_id: uuid.UUID
