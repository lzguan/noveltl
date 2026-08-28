from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from src.memory.access import MemAccessContext


class UUIDCache:
    """A simple class to translate UUIDs to and from strings."""

    def __init__(self):
        self.uuid_to_str: dict[UUID, str] = {}
        self.str_to_uuid: dict[str, UUID] = {}
        self.counter: int = 0

    def gen_str(self) -> str:
        """Generate a new unique string representation of a UUID."""
        self.counter += 1
        return f"m{self.counter}"

    def new(self, uuid: UUID) -> str:
        """Add a new UUID to the cache and return its string representation."""
        if uuid not in self.uuid_to_str:
            str_uuid = self.gen_str()
            self.uuid_to_str[uuid] = str_uuid
            self.str_to_uuid[str_uuid] = uuid
        return self.uuid_to_str[uuid]

    def get_str(self, uuid: UUID) -> str:
        """Get the string representation of a UUID."""
        if uuid in self.uuid_to_str:
            return self.uuid_to_str[uuid]
        raise KeyError(f"UUID {uuid} not found in the cache.")

    def get_uuid(self, str_uuid: str) -> UUID:
        """Get the UUID corresponding to a string representation."""
        if str_uuid in self.str_to_uuid:
            return self.str_to_uuid[str_uuid]
        raise KeyError(f"String {str_uuid} not found in the cache.")


@dataclass
class MemAgentDeps:
    db: Session
    mem_access_context: MemAccessContext
    initial_plugin_contexts: dict[str, str] = field(default_factory=dict)
    uuid_cache: UUIDCache = field(default_factory=UUIDCache)
