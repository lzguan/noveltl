"""Schemas for glossary context exposed to memory agents."""

from uuid import UUID

from pydantic import ConfigDict, Field

from src.memory.schemas import AgentMemory
from src.memory.types import ReviewStatus
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
