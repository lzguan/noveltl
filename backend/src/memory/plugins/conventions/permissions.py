from typing import Any

from sqlalchemy import Delete, Select, Update, exists, select
from sqlalchemy.orm import aliased
from sqlalchemy.sql.dml import ReturningDelete

from src.auth.models import User
from src.memory.models import MemoryGroup
from src.memory.permissions import memory_group_mod_access_select
from src.memory.plugins.conventions.models import TranslationConvention


def convention_mod_access_select[T: Select[*tuple[Any, ...]]](
    stmt: T,
    current_user: User | None,
    aliased_type: type[TranslationConvention] = TranslationConvention,
    *,
    edit_only: bool = False,
) -> T:
    group_alias = aliased(MemoryGroup)
    group_access = (
        select(1)
        .select_from(group_alias)
        .where(group_alias.memory_group_id == aliased_type.memory_group_id)
        .correlate(aliased_type)
    )
    group_access = memory_group_mod_access_select(
        group_access,
        current_user,
        group_alias,
        edit_only=edit_only,
    )
    return stmt.where(exists(group_access))


def convention_mod_access_update[T: Update](
    stmt: T,
    current_user: User,
    aliased_type: type[TranslationConvention] = TranslationConvention,
) -> T:
    group_alias = aliased(MemoryGroup)
    group_access = (
        select(1)
        .select_from(group_alias)
        .where(group_alias.memory_group_id == aliased_type.memory_group_id)
        .correlate(aliased_type)
    )
    group_access = memory_group_mod_access_select(
        group_access,
        current_user,
        group_alias,
        edit_only=True,
    )
    return stmt.where(exists(group_access))


def convention_mod_access_delete[T: Delete | ReturningDelete[Any]](
    stmt: T,
    current_user: User,
    aliased_type: type[TranslationConvention] = TranslationConvention,
) -> T:
    group_alias = aliased(MemoryGroup)
    group_access = (
        select(1)
        .select_from(group_alias)
        .where(group_alias.memory_group_id == aliased_type.memory_group_id)
        .correlate(aliased_type)
    )
    group_access = memory_group_mod_access_select(
        group_access,
        current_user,
        group_alias,
        edit_only=True,
    )
    return stmt.where(exists(group_access))
