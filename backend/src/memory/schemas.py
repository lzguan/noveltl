"""Schemas for context exposed to memory agents."""

from pydantic import ConfigDict, Field

from src.memory.types import MemoryType, ReviewStatus
from src.schemas import Model


class MemoryGroupContext(Model):
    """Memory-group metadata relevant to an agent run."""

    memory_language: str = Field(description="Language in which memory content should be written.")


class Memory[KeyT](Model):
    """A memory represented as context for an agent."""

    model_config = ConfigDict(from_attributes=True)

    memory_id: KeyT = Field(
        description="Stable identifier to use when superseding, expiring, or otherwise referring to this memory."
    )
    memory_type: MemoryType = Field(description="Kind of information stored: a fact, event, definition, or relation.")
    memory_content: str = Field(
        description="The contextual information that should inform glossary maintenance and novel continuity."
    )
    memory_start_num: int = Field(
        description="First chapter number for which this memory is applicable; larger values indicate newer information."
    )
    memory_review_status: ReviewStatus = Field(
        description="Human-review state of the memory. Pending memories are unverified; approved memories are verified."
    )
    memory_end_num: int | None = Field(
        repr=False,
        description="Exclusive ending chapter number stored by the database, or null when the memory does not expire.",
    )
