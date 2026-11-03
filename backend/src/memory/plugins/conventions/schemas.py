from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import ConfigDict, StringConstraints

from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.types import Creator, ReviewStatus
from src.schemas import Model, Page


class ConventionRead(Model):
    model_config = ConfigDict(from_attributes=True)

    convention_id: UUID
    memory_group_id: UUID
    category: ConventionCategory
    title: str
    rule: str
    rationale: str | None
    review_status: ReviewStatus
    creator_type: Creator
    created_at: datetime
    updated_at: datetime


ConventionPage = Page[ConventionRead]


class SaveConvention(Model):
    """Full convention content, used for both creation and replacement."""

    category: ConventionCategory
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    rule: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    rationale: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None = None
