from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from src.memory.access import MemAccessContext


@dataclass
class MemAgentDeps:
    db_factory: sessionmaker[Session]
    mem_access_context: MemAccessContext
    job_id: UUID
