"""Schemas for glossary context exposed to memory agents."""

from uuid import UUID

from pydantic import ConfigDict, Field

from src.memory.schemas import AgentMemory, Memory
from src.memory.types import MemoryType, ReviewStatus, Scope
from src.schemas import Model


class GlossaryTerm(Model):
    """A glossary term represented as context for an agent."""

    model_config = ConfigDict(from_attributes=True)

    term_id: UUID = Field(
        description="Stable identifier to use when creating memories for or changing the review state of this term."
    )
    term: str = Field(description="Term exactly as it appears in the novel's source text.")
    review_status: ReviewStatus = Field(
        description="Human-review state of the term. Pending terms are unverified; approved terms are verified."
    )


class GlossaryMemory[KeyT](Model):
    """A memory together with the glossary terms it describes."""

    memory: AgentMemory[KeyT] = Field(description="The memory that describes the glossary terms.")
    terms: list[GlossaryTerm] = Field(
        description="Glossary terms described by this memory; one memory may apply to multiple related terms."
    )


class GlossaryMemoryDetail(Model):
    memory: Memory
    terms: list[GlossaryTerm]


class GlossaryMemoryPage(Model):
    count: int = Field(ge=0)
    rows: list[GlossaryMemoryDetail]


class GlossaryTermPage(Model):
    count: int = Field(ge=0)
    rows: list[GlossaryTerm]


class CreateGlossaryMemory(Model):
    chapter_id: UUID
    chapter_content_id: UUID
    memory_type: MemoryType
    memory_content: str = Field(min_length=1)
    term_ids: list[UUID] = Field(min_length=1)
    scope: Scope | None = None


class CreateGlossaryTerm(Model):
    term: str = Field(min_length=1, max_length=100)


class UpdateGlossaryTerm(Model):
    term: str = Field(min_length=1, max_length=100)


class ReplaceGlossaryAssociations(Model):
    term_ids: list[UUID]
