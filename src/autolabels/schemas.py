"""
Pydantic schemas for autolabels.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import List, Dict, Tuple
from ..labels.schemas import Label
from .constants import *

class NERModelParamsBase(BaseModel):
    """
    Pydantic schema for base NER model parameters. No attributes provided.
    """
    pass

class ChunkingNERModelParamsBase(NERModelParamsBase):
    """
    Pydantic schema for base chunking NER model parameters.
    """
    chunk_size : int
    separators : List[str] = Field(default=['\n', '。', '！', '？', '.', '!', '?'])
    force_chunk : bool = Field(default=False)

class AutoLabel(BaseModel):
    """
    Pydantic schema for an auto-labeled data entry.

    Attributes:
        auto_label_id: Integer identifier for this AutoLabel.
        auto_label_data: Dictionary containing the auto-labeled data.
        auto_label_model_name: Name of the model used to generate the auto labels.
        auto_label_model_params: Parameters used for the model to generate the auto labels.
        auto_label_model_is_deterministic: Whether the model is deterministic.
        auto_label_status: Labeling progress for this autolabel.
        auto_label_message: Details on status.
        raw_chapter_revision_id: Chapter this AutoLabel is associated with.
    """
    model_config = ConfigDict(from_attributes=True)
    auto_label_id : int
    auto_label_data : List[Label] | None
    auto_label_model_name : str
    auto_label_model_params : Dict[str, str | int | float | bool]
    auto_label_status : AutoLabelProgress
    auto_label_message : str | None = None
    raw_chapter_revision_id : int

class AutoLabelMeta(BaseModel):
    """
    Pydantic schema for auto-label metadata.

    Attributes:
        auto_label_id: Integer identifier for this AutoLabel.
        auto_label_model_name: Name of the model used to generate the auto labels.
        auto_label_model_params: Parameters used for the model to generate the auto labels.
        auto_label_model_is_deterministic: Whether the model is deterministic.
        auto_label_status: Labeling progress for this autolabel.
        auto_label_message: Details on status.
        raw_chapter_revision_id: Chapter this AutoLabel is associated with.
    """
    model_config = ConfigDict(from_attributes=True)

    auto_label_id : int
    auto_label_model_name : str
    auto_label_model_params : Dict[str, str | int | float | bool]
    auto_label_status : AutoLabelProgress
    auto_label_message : str | None = None
    raw_chapter_revision_id : int

class CreateAutoLabels(BaseModel):
    """
    Pydantic schema for creating an auto-labeled data entry.

    Attributes:
        raw_chapter_revision_ids: Chapters to create autolabels for
        auto_label_model_name: Name of the model used to generate the auto labels.
        auto_label_model_params: Parameters used for the model to generate the auto labels.
    """
    raw_chapter_revision_ids : List[int]
    auto_label_model_name : str
    auto_label_model_params : Dict[str, str | int | float | bool]

class CreateAutoLabelsStatus(BaseModel):
    """
    Pydantic schema for return message upon an auto label create request.

    Attributes:
        inserts: Dictionary of {revision_id: (Metadata, success/fail)} for newly created labels.
        exists: Dictionary of {revision_id: Metadata} for labels that already existed.
    """
    inserts : Dict[int, Tuple[AutoLabelMeta, bool]]
    exists : Dict[int, AutoLabelMeta]