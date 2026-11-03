from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import ConfigDict, StringConstraints

from src.memory.types import Creator, ReviewStatus
from src.schemas import Model


class TermTranslation(Model):
    """A canonical rendering for one exact source form in the group's language."""

    term: str
    translation: str
    review_status: ReviewStatus


class TermTranslationRead(Model):
    model_config = ConfigDict(from_attributes=True)

    term_id: UUID
    translation: str
    review_status: ReviewStatus
    creator_type: Creator
    created_at: datetime
    updated_at: datetime


class SaveTermTranslation(Model):
    translation: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
