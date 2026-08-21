from typing import Any

from sqlalchemy import Select, Update, exists, select
from sqlalchemy.orm import aliased

from src.auth.models import User
from src.memory.models import Memory, MemoryGroup
from src.novels.models import Novel
from src.novels.permissions import novel_mod_access_select


def memory_group_mod_access_select[T: Select[tuple[Any, ...]]](
    stmt: T,
    current_user: User | None,
    aliased_type: type[MemoryGroup] = MemoryGroup,
    *,
    edit_only: bool = False,
) -> T:
    """Restrict a memory-group select through its corresponding novel."""
    novel_alias = aliased(Novel)
    novel_access = (
        select(1).select_from(novel_alias).where(novel_alias.novel_id == aliased_type.novel_id).correlate(aliased_type)
    )
    novel_access = novel_mod_access_select(
        novel_access,
        current_user,
        novel_alias,
        edit_only=edit_only,
    )
    return stmt.where(exists(novel_access))


def memory_mod_access_select[T: Select[tuple[Any, ...]]](
    stmt: T,
    current_user: User | None,
    aliased_type: type[Memory] = Memory,
    *,
    edit_only: bool = False,
) -> T:
    """Restrict a memory select through its memory group's corresponding novel."""
    memory_group_alias = aliased(MemoryGroup)
    memory_group_access = (
        select(1)
        .select_from(memory_group_alias)
        .where(memory_group_alias.memory_group_id == aliased_type.memory_group_id)
        .correlate(aliased_type)
    )
    memory_group_access = memory_group_mod_access_select(
        memory_group_access,
        current_user,
        memory_group_alias,
        edit_only=edit_only,
    )
    return stmt.where(exists(memory_group_access))


def memory_mod_access_update[T: Update](
    stmt: T,
    current_user: User,
    aliased_type: type[Memory] = Memory,
):
    """Restrict a memory update through its memory group's corresponding novel."""
    memory_group_alias = aliased(MemoryGroup)
    memory_group_access = (
        select(1)
        .select_from(memory_group_alias)
        .where(memory_group_alias.memory_group_id == aliased_type.memory_group_id)
        .correlate(aliased_type)
    )
    memory_group_access = memory_group_mod_access_select(
        memory_group_access,
        current_user,
        memory_group_alias,
        edit_only=True,
    )
    return stmt.where(exists(memory_group_access))
