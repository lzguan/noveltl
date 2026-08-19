from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from src.memory.access import MemAccessContext


@dataclass
class MemAgentDeps:
    db_factory: sessionmaker[Session]
    mem_access_context: MemAccessContext
    job_id: UUID
    initial_plugin_contexts: dict[str, str] = field(default_factory=dict)
