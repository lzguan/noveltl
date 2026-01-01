"""
Pydantic schemas for autolabels.
"""
from ..schemas import SkipDefaultModel
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import List, Dict, Tuple, Self
from ..labels.schemas import Label
from .constants import *
from .config import *
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

    chunk_size : int = Field(default=500, gt=0, le=512)
    separators : Dict[str, SepPriority] = Field(
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
            ":": SepPriority.LOW
        })
    force_chunk : bool = False
    @model_validator(mode='after')
    def verify_separators(self) -> Self:
        if self.separators is not None and not all(len(key) == 1 for key in self.separators):
            raise ValueError("A separator does not have length 1")
        return self


class AutoLabel(BaseModel):
    """
    Pydantic schema for an auto-labeled data entry.

    Attributes:
        auto_label_id: Integer identifier for this AutoLabel.
        auto_label_data: Dictionary containing the auto-labeled data.
        auto_label_model_name: Name of the model used to generate the auto labels.
        auto_label_model_params: Parameters used for the model to generate the auto labels.
        auto_label_status: Labeling progress for this autolabel.
        auto_label_message: Details on status.
        raw_chapter_revision_id: Chapter this AutoLabel is associated with.
        auto_label_last_job_id: Job id of last job that was run on this AutoLabel.
    """
    model_config = ConfigDict(from_attributes=True)
    auto_label_id : int
    auto_label_data : List[Label] | None
    auto_label_model_name : str
    auto_label_model_params : SmallDict = Field(max_length=MAX_PARAMS_FIELDS)
    auto_label_status : AutoLabelProgress
    auto_label_message : str | None = None
    raw_chapter_revision_id : int
    auto_label_last_job_id : str

class AutoLabelMeta(BaseModel):
    """
    Pydantic schema for auto-label metadata.

    Attributes:
        auto_label_id: Integer identifier for this AutoLabel.
        auto_label_model_name: Name of the model used to generate the auto labels.
        auto_label_model_params: Parameters used for the model to generate the auto labels.
        auto_label_status: Labeling progress for this autolabel.
        auto_label_message: Details on status.
        raw_chapter_revision_id: Chapter this AutoLabel is associated with.
        auto_label_last_job_id: Job id of last job that was run on this AutoLabel.
    """
    model_config = ConfigDict(from_attributes=True)

    auto_label_id : int
    auto_label_model_name : str
    auto_label_model_params : SmallDict = Field(max_length=MAX_PARAMS_FIELDS)
    auto_label_status : AutoLabelProgress
    auto_label_message : str | None = None
    raw_chapter_revision_id : int
    auto_label_last_job_id : str

class CreateAutoLabels(BaseModel):
    """
    Pydantic schema for creating an auto-labeled data entry.

    Attributes:
        novel_id: Id of novel to create auto labels for.
        auto_label_model_name: Name of the model used to generate the auto labels.
        auto_label_model_params: Parameters used for the model to generate the auto labels.
        raw_chapter_ids: Optional parameter. Restrict to revisions with specific raw chapter ids.
        raw_chapter_revision_ids: Optional parameter. Restrict to revisions with specific raw chapter revision ids. 
        start: Optional parameter. Restrict to revisions with raw chapter num >= start.
        end: Optional parameter. Restrict to revisions with raw chapter num < end.
        is_primary: Optional paremter. Restrict to revisions with this specific primary flag.
        is_public: Optional parameter. Restrict to revisions with this specific public flag.

    """
    novel_id : int
    auto_label_model_name : str
    auto_label_model_params : SmallDict = Field(max_length=MAX_PARAMS_FIELDS)
    raw_chapter_ids : List[int] | None = None
    raw_chapter_revision_ids : List[int] | None = None
    start : int | None = None
    end : int | None = None
    is_primary : bool | None = None
    is_public : bool | None = None

    @model_validator(mode='after')
    def validate_model_params(self) -> Self:
        if self.auto_label_model_name == 'cluener':
            resolved_params = CluenerModelParams.model_validate(self.auto_label_model_params)
            self.auto_label_model_params = resolved_params.model_dump()
        
        # Add 'elif' blocks here for other models (e.g., 'gpt4', 'bert')
        
        return self

class CreateAutoLabelsStatus(BaseModel):
    """
    Pydantic schema for return message upon an auto label create request.

    Attributes:
        inserts: Dictionary of {revision_id: (Metadata, success/fail)} for newly created labels.
        exists: Dictionary of {revision_id: Metadata} for labels that already existed.
    """
    inserts : Dict[int, Tuple[AutoLabelMeta, bool]]
    exists : Dict[int, AutoLabelMeta]