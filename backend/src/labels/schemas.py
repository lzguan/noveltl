"""
Pydantic schemas for labels.
"""

import uuid
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..autolabels.constants import MAX_PARAMS_FIELDS
from ..autolabels.validators import SmallDict
from .constants import MAX_LABEL_ENTITY_GROUP_NAME_LEN, MAX_LABEL_GROUP_NAME_LEN, MAX_LABEL_WORD_LEN


class LabelGroup(BaseModel):
    """
    Pydantic schema for a label group.

    Attributes:
        label_group_id: UUID identifier for this label group.
        label_group_name: Name of this label group.
        novel_id: UUID of novel this label group belongs to.
    """
    model_config = ConfigDict(from_attributes=True)

    label_group_id : uuid.UUID
    label_group_name : str = Field(max_length=MAX_LABEL_GROUP_NAME_LEN)
    novel_id : uuid.UUID

class CreateLabelGroup(BaseModel):
    """
    Pydantic schema for validating forms for creating a label group.

    Attributes:
        label_group_name: Name of label group to create.
        novel_id: UUID of novel this label group belongs to.
    """
    label_group_name : str = Field(max_length=MAX_LABEL_GROUP_NAME_LEN)
    novel_id : uuid.UUID

class UpdateLabelGroup(BaseModel):
    """
    Pydantic schema for validating forms for updating a label group.

    Attributes:
        label_group_name: New name of label group.
    """
    label_group_name : str = Field(max_length=MAX_LABEL_GROUP_NAME_LEN)

class LabelData(BaseModel):
    """
    Pydantic schema for a list of labels in some text.

    Attributes:
        label_data_id: UUID identifier for this LabelData.
        label_group_id: UUID of label group this LabelData belongs to.
        chapter_content_id: UUID of chapter content this LabelData is labelling.
    """
    model_config = ConfigDict(from_attributes=True)
    label_data_id : uuid.UUID

    label_group_id : uuid.UUID
    chapter_content_id : uuid.UUID

class LabelBase(BaseModel):
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
    label_entity_group : str | None = Field(max_length=MAX_LABEL_ENTITY_GROUP_NAME_LEN)
    label_score : float = Field(ge=0.0, le=1.0)
    label_word : str = Field(max_length=MAX_LABEL_WORD_LEN)
    label_start : int = Field(ge=0)
    label_end : int = Field(ge=0)
    label_dirty : bool

    @model_validator(mode='after')
    def check_start_lt_end(self) -> Self:
        if self.label_start >= self.label_end:
            raise ValueError("Label start must be less than label end")
        return self

    @model_validator(mode='after')
    def check_word_len(self) -> Self:
        if len(self.label_word) != self.label_end - self.label_start:
            raise ValueError("Length of label word does not match label bounds")
        return self

    def __repr__(self) -> str:
        return f"{{label_word : {self.label_word},label_entity_group : {self.label_entity_group},label_start : {self.label_start},label_end : {self.label_end},label_score : {self.label_score},label_entity_group : {self.label_entity_group}}}"

class Label(LabelBase):
    """
    Pydantic schema for a label that belongs to a LabelData.
    Extends LabelBase with a label_data_id foreign key.
    """
    label_data_id : uuid.UUID

class CreateLabelData(BaseModel):
    """
    Pydantic schema for validating create requests for label data.

    Attributes:
        chapter_content_id: UUID of chapter content being labelled.
    """
    chapter_content_id : uuid.UUID

class LabelOpBase(BaseModel):
    """
    Base class for a label operation. Any label operation must include these parameters to validate the request.

    Attributes:
        start_pos: Start position of label to be operated on/created/...
        end_pos: End position of label to be operated on/created/...
        word: Word this label is labelling. Note that in order for any label operation to be valid, we must have chapter_text[start_pos:end_pos] == word.
    """
    start_pos : int = Field(ge=0)
    end_pos : int = Field(ge=0)
    word : str = Field(max_length=MAX_LABEL_WORD_LEN)

    @model_validator(mode='after')
    def check_start_lt_end(self) -> Self:
        if self.start_pos >= self.end_pos:
            raise ValueError("Label start must be less than label end")
        return self

    @model_validator(mode='after')
    def check_word_len(self) -> Self:
        if len(self.word) != self.end_pos - self.start_pos:
            raise ValueError("Length of word does not match label bounds")
        return self

class AddLabelOp(LabelOpBase):
    """
    Pydantic schema for a label add operation. Inherits all attributes from LabelOpBase.

    Attributes:
        op: The string literal 'add'.
        dirty: Boolean whether to mark the label as dirty.
        entity_group: String representing what entity group this label belongs to. If none, then set a default value.
        score: Float score between 0.0 and 1.0 representing how likely this label is to be an entity.
    """
    op : Literal['add']
    dirty : bool = True
    entity_group : str | None = Field(default=None, max_length=MAX_LABEL_ENTITY_GROUP_NAME_LEN)
    score : float = Field(default=1.0, ge = 0.0, le = 1.0)

class DeleteLabelOp(LabelOpBase):
    """
    Pydantic schema for a label delete operation. Inherits all attributes from LabelOpBase.

    Attributes:
        op: The string literal 'delete'.
    """
    op : Literal['delete']

class UpdateLabelOp(LabelOpBase):
    """
    Pydantic schema for a label update operation. Inherits all attributes from LabelOpBase.

    Attributes:
        op: The string literal 'update'.
        new_start_pos: Optional parameter. The new start position of the label.
        new_end_pos: Optional parameter. The new end position of the label.
        new_word: Optional parameter. The new word the label is labelling. Must satisfy `new_word == chapter_text[new_start_pos : new_end_pos]`.
        dirty: Optional parameter. Value to change the current label's dirty value to.
        entity_group: Optional parameter. New entity group for this label.
        score: Optional parameter. New score for the entity.
    """
    op : Literal['update']
    new_start_pos : int | None = Field(default=None, ge=0)
    new_end_pos : int | None = Field(default=None, ge=0)
    new_word : str | None = Field(default=None, max_length=MAX_LABEL_WORD_LEN)
    dirty : bool | None = None
    entity_group : str | None = Field(default=None, max_length=MAX_LABEL_ENTITY_GROUP_NAME_LEN)
    score : float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode='after')
    def check_new_start_lt_new_end(self) -> Self:
        cur_start = self.new_start_pos if self.new_start_pos is not None else self.start_pos
        cur_end = self.new_end_pos if self.new_end_pos is not None else self.end_pos
        if cur_start >= cur_end:
            raise ValueError("Start pos must be less than end pos")
        return self

    @model_validator(mode='after')
    def check_new_word_len(self) -> Self:
        if self.new_word is None:
            if self.new_end_pos is not None or self.new_start_pos is not None:
                raise ValueError("New word not defined when label bounds changed")
            return self
        cur_start = self.new_start_pos if self.new_start_pos is not None else self.start_pos
        cur_end = self.new_end_pos if self.new_end_pos is not None else self.end_pos
        if len(self.new_word) != cur_end - cur_start:
            raise ValueError("Length of new word does not match label bounds")
        return self

class UpdateLabelDataStream(BaseModel):
    """
    Pydantic schema for a buffered stream of label operations.

    Attributes:
        ops: A list of label operations.
    """
    ops : list[Annotated[AddLabelOp | DeleteLabelOp | UpdateLabelOp, Field(discriminator='op')]]


class CreateLabelDataByAutoLabel(BaseModel):
    """
    Pydantic schema to specifiy a set of AutoLabels to be moved to LabelDatas.

    Attributes:
        model_name: Name of NER model that performed the autolabeling.
        model_params: Parameters of model used.
        chapter_ids: Optional filter on what chapters to include.
        start: Optional filter on the least chapter number to include.
        end: Optional filter on the greatest chapter number to include.
    """
    model_name : str
    model_params : SmallDict = Field(max_length=MAX_PARAMS_FIELDS)
    chapter_ids : list[uuid.UUID] | None = None
    start : int | None = None
    end : int | None = None

class CreateLabelDataByAutoLabelStatus(BaseModel):
    """
    Return message for CreateLabelDataByAutoLabel.

    Attributes:
        success: List of tuples of (chapter_id, chapter_content_id) for successful inserts.
        errors: List of tuples of (chapter_id, chapter_content_id, error message) for failed inserts.
    """
    success : list[tuple[uuid.UUID, uuid.UUID]]
    errors: list[tuple[uuid.UUID, uuid.UUID, str]]
