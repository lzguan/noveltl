from typing import Any
from uuid import UUID

from sqlalchemy import func, inspect, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.memory.exceptions import MemoryWorkspaceNotFoundException
from src.memory.models import MemoryJob
from src.memory.shadow_models import MemoryWorkspace
from src.model_base import Base


def check_workspace(db: Session, workspace_id: UUID, memory_group_id: UUID, chapter_id: UUID | None = None) -> None:
    query = (
        select(MemoryWorkspace.workspace_id)
        .join(MemoryJob, MemoryJob.memory_job_id == MemoryWorkspace.memory_job_id)
        .where(MemoryWorkspace.workspace_id == workspace_id, MemoryJob.memory_group_id == memory_group_id)
    )
    if chapter_id is not None:
        query = query.where(MemoryWorkspace.chapter_id == chapter_id)
    if db.scalar(query) is None:
        raise MemoryWorkspaceNotFoundException("Workspace does not exist or belongs to a different group or chapter")


def stage_record[T: Base](
    db: Session, shadow: type[T], workspace_id: UUID, original: Base | None = None, **values: Any
) -> T:
    payload = (
        {column.name: getattr(original, column.name) for column in inspect(type(original)).columns}
        if original is not None
        else {}
    )
    payload.update(workspace_id=workspace_id, deleted=False, updated_at=func.now())
    payload.update(values)
    statement = insert(shadow).values(**payload)
    primary_key = {column.name for column in inspect(shadow).primary_key}
    statement = statement.on_conflict_do_update(
        index_elements=[column.name for column in inspect(shadow).primary_key],
        set_={name: statement.excluded[name] for name in payload if name not in primary_key},
    ).returning(shadow)
    return db.execute(statement.execution_options(populate_existing=True)).scalar_one()
