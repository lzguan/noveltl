"""Schemas for context exposed to memory agents."""

from uuid import UUID

from pydantic import ConfigDict, Field

from src.memory.types import Creator, MemoryType, PluginName, ReviewStatus
from src.schemas import Model


class MemoryGroupContext(Model):
    """Memory-group metadata relevant to an agent run."""

    memory_language: str = Field(description="Language in which memory content should be written.")


class AgentMemory[KeyT](Model):
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


class Memory(Model):
    """Memory schema"""

    model_config = ConfigDict(from_attributes=True)

    memory_id: UUID = Field(
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
    supersedes_memory_id: UUID | None = Field(
        repr=False,
        description="Identifier of the memory that this memory supersedes, or null when this memory is not a superseding memory.",
    )
    creator_type: Creator = Field(
        description="Type of entity that created the memory: a human, an AI agent, or a workflow."
    )
    plugin_name: PluginName = Field(description="Name of the plugin that owns the memory.")


class MemoryGroup(Model):
    """Memory group schema"""

    model_config = ConfigDict(from_attributes=True)

    memory_group_id: UUID = Field(description="Stable identifier to use when referring to this memory group.")
    memory_group_name: str = Field(description="Human-readable name of the memory group.")
    novel_id: UUID = Field(description="Identifier of the novel to which this memory group belongs.")
    memory_language: str = Field(description="Language in which memory content should be written.")


class MemoryPage(Model):
    count: int = Field(ge=0)
    rows: list[Memory]


class UpdateMemoryContent(Model):
    memory_content: str = Field(min_length=1)


class UpdateReviewStatus(Model):
    review_status: ReviewStatus


class ExpireMemory(Model):
    chapter_id: UUID
