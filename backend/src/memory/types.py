from enum import StrEnum
from typing import Literal


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
    RELATION: Long-term memory about a relationship between glossary terms.
    """

    FACT = "fact"
    EVENT = "event"
    DEFINITION = "def"
    RELATION = "rel"


class Scope(StrEnum):
    """
    The scope of a memory (i.e. how long it should be retained).

    LOCAL: Memory is only relevant to the current chapter.
    RECENT: Memory is relevant to the current chapter and a few subsequent chapters.
    PERSIST: Memory is relevant to all chapters and should be retained indefinitely until explicitly superseded or expired.
    """

    LOCAL = "local"
    RECENT = "recent"
    PERSIST = "persist"


type PluginName = Literal["glossary"]


class JobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
