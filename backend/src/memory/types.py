from enum import StrEnum


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Creator(StrEnum):
    USER = "user"
    WORKFLOW = "workflow"
    AGENT = "agent"


class MemoryType(StrEnum):
    """
    The type of a memory.

    FACT: Memory about a specific fact or piece of information.
    EVENT: Memory about a specific event or occurrence.
    DEFINITION: Long-term memory about a specific definition or concept.
    TRANSLATION: Long-term memory about a specific translation or mapping.
    """

    FACT = "fact"
    EVENT = "event"
    DEFINITION = "def"
    TRANSLATION = "tl"


class Scope(StrEnum):
    LOCAL = "local"
    RECENT = "recent"
    PERSIST = "persist"
