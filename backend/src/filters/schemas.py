"""
Common schemas for filters, including context and instance schemas. These are used across different filter implementations to standardize the data structures for contexts and instances.
"""

import uuid
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator

from ..labels import schemas as label_schemas


# -----------------------------------------
# --- Abstract base schemas for filters ---
# -----------------------------------------
class InstanceBase(BaseModel):
    pass

class ContextBase(BaseModel):
    pass

class FlagInstancesOptionsBase(BaseModel):
    pass

class GetContextsOptionsBase(BaseModel):
    pass

class DecideInstancesOptionsBase(BaseModel):
    pass

class ApplyFilterOptionsBase(BaseModel):
    create_copy : bool = Field(
        default=False,
        description="Whether to copy the labels that pass the filter instead of moving them. If set to True, new labels will be created with the same label word and entity group as the original label. If set to False, apply_filter will update the original labels that pass the filter. This option is only applicable to filters that support applying, and will be ignored for filters that don't support applying. Read specific implementations of apply_filter for details on how this option affects the behavior of the filter when applying."
    )
    new_label_group_name : str | None = Field(
        default=None,
        description="If provided and create_copy is True, a new label group with this name will be created and the new labels created by applying the filter will be added to this group. If not provided, the new labels will not be added to any group."
    )

    @model_validator(mode="after")
    def check_new_label_group_name(self) -> Self:
        if self.create_copy and self.new_label_group_name is None:
            raise ValueError("new_label_group_name must be provided when create_copy is True")
        return self


# --------------------------------------
# --- Commonly used concrete schemas ---
# --------------------------------------

class SentenceContext(ContextBase):
    type : Literal["sentence"] = "sentence"
    text : str = Field(..., description="The sentence text containing the label.")
    label_start_rel : int = Field(..., description="The start index of the label within the sentence text.")
    label_end_rel : int = Field(..., description="The end index of the label within the sentence text.")
    label : label_schemas.Label | None = Field(default=None, description="The label associated with this context, if flagged to return.")
    chapter_content_id : uuid.UUID

class ParagraphContext(ContextBase):
    type : Literal["paragraph"] = "paragraph"
    text : str = Field(..., description="The paragraph text containing the label.")
    label_start_rel : int = Field(..., description="The start index of the label within the paragraph text.")
    label_end_rel : int = Field(..., description="The end index of the label within the paragraph text.")
    label : label_schemas.Label | None = Field(default=None, description="The label associated with this context, if flagged to return.")
    chapter_content_id : uuid.UUID

class SingleLabel(InstanceBase):
    type : Literal["single_label"] = "single_label"
    label : label_schemas.Label
    chapter_content_id : uuid.UUID


# --------------------------------------
# ------ Router schemas and types ------
# --------------------------------------

class InstanceOptions(BaseModel):
    instances: list[Any]
    options : dict[Any, Any]

class InstanceContextOptions(BaseModel):
    instance_contexts: list[tuple[Any, Any]]
    options : dict[Any, Any]
