"""Schemas for glossary context exposed to memory agents."""

from uuid import UUID

from pydantic import ConfigDict, Field

from src.memory.plugins.glossary.types import TermKind
from src.memory.schemas import AgentMemory, AgentModel, Memory
from src.memory.types import MemoryType, ReviewStatus, Scope
from src.schemas import Model, Page


class AgentGlossaryTerm(AgentModel):
    """A glossary term represented as context for an agent."""

    model_config = ConfigDict(from_attributes=True)

    term: str = Field(description="Term exactly as it appears in the novel's source text.")
    term_kind: TermKind | None = Field(
        description="Semantic kind of the glossary term, or null when it has not been categorized."
    )
    review_status: ReviewStatus = Field(
        description="Human-review state of the term. Pending terms are unverified; approved terms are verified."
    )


class AgentGlossaryMemory[KeyT](AgentModel):
    """A memory together with the glossary terms it describes."""

    memory: AgentMemory[KeyT] = Field(description="The memory that describes the glossary terms.")
    terms: list[AgentGlossaryTerm] = Field(
        description="Glossary terms described by this memory; one memory may apply to multiple related terms."
    )


class GlossaryTerm(Model):
    """A glossary term represented as context for an agent."""

    model_config = ConfigDict(from_attributes=True)
    term_id: UUID = Field(description="Stable identifier for the glossary term.")
    term: str = Field(description="Term exactly as it appears in the novel's source text.")
    term_kind: TermKind | None = Field(
        description="Semantic kind of the glossary term, or null when it has not been categorized."
    )
    review_status: ReviewStatus = Field(
        description="Human-review state of the term. Pending terms are unverified; approved terms are verified."
    )


class GlossaryTermSummary(GlossaryTerm):
    """A glossary term together with its associated-memory count in the requested scope."""

    associated_memory_count: int = Field(ge=0)


class GlossaryMemory(Model):
    """A memory together with the glossary terms it describes."""

    model_config = ConfigDict(from_attributes=True)

    memory: Memory = Field(description="The memory that describes the glossary terms.")
    terms: list[GlossaryTerm] = Field(
        description="Glossary terms described by this memory; one memory may apply to multiple related terms."
    )


GlossaryMemoryPage = Page[GlossaryMemory]


GlossaryTermPage = Page[GlossaryTermSummary]


class CreateGlossaryMemory(Model):
    chapter_id: UUID
    chapter_content_id: UUID
    memory_type: MemoryType
    mark: str | None = Field(default=None, min_length=1)
    memory_content: str = Field(min_length=1)
    term_ids: list[UUID] = Field(min_length=1)
    scope: Scope | None = None


class CreateGlossaryTerm(Model):
    term: str = Field(min_length=1, max_length=100)
    term_kind: TermKind | None = None


class UpdateGlossaryTerm(Model):
    term: str = Field(min_length=1, max_length=100)
    term_kind: TermKind | None = None


class ReplaceGlossaryAssociations(Model):
    term_ids: list[UUID]
