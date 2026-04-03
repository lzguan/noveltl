"""
Pydantic schemas for novel translation jobs.
"""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from .constants import (
    MAX_LANGUAGE_CODE_LEN,
    MAX_MODEL_NAME_LEN,
    ChapterTranslationStatus,
    NovelTranslationStatus,
)


class NovelTranslationJob(BaseModel):
    """
    Pydantic schema for a novel translation job.
    """

    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    source_novel_id: uuid.UUID
    target_novel_id: uuid.UUID | None = None
    glossary_id: uuid.UUID | None = None
    status: NovelTranslationStatus
    job_model_name: str | None = Field(default=None, max_length=MAX_MODEL_NAME_LEN)
    job_last_job_id: uuid.UUID | None = None
    job_message: str | None = None
    chapters_translated: int
    chapters_total: int
    target_language_code: str = Field(max_length=MAX_LANGUAGE_CODE_LEN)


class NovelTranslationJobWithMappings(BaseModel):
    """
    Pydantic schema for a novel translation job with chapter mappings included.
    """

    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    source_novel_id: uuid.UUID
    target_novel_id: uuid.UUID | None = None
    glossary_id: uuid.UUID | None = None
    status: NovelTranslationStatus
    job_model_name: str | None = Field(default=None, max_length=MAX_MODEL_NAME_LEN)
    job_last_job_id: uuid.UUID | None = None
    job_message: str | None = None
    chapters_translated: int
    chapters_total: int
    target_language_code: str = Field(max_length=MAX_LANGUAGE_CODE_LEN)
    chapter_mappings_with_job: list["ChapterTranslationMapping"]


class CreateNovelTranslationJob(BaseModel):
    """
    Pydantic schema for requesting a novel translation job.
    """

    source_novel_id: uuid.UUID
    glossary_id: uuid.UUID | None = None
    target_language_code: str = Field(max_length=MAX_LANGUAGE_CODE_LEN)
    model_name: str | None = Field(default=None, max_length=MAX_MODEL_NAME_LEN)


class ChapterTranslationMapping(BaseModel):
    """
    Pydantic schema for a per-chapter translation mapping.
    """

    model_config = ConfigDict(from_attributes=True)

    mapping_id: uuid.UUID
    job_id: uuid.UUID
    source_chapter_id: uuid.UUID
    target_chapter_id: uuid.UUID | None = None
    status: ChapterTranslationStatus
    mapping_message: str | None = None
