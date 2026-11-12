from uuid import UUID

from sqlalchemy import Select, inspect, select, union_all
from sqlalchemy.orm import aliased
from sqlalchemy.orm.util import AliasedClass

from src.model_base import Base


def visible_rows[T: Base](
    published: type[T], shadow: type[Base], workspace_id: UUID | None
) -> type[T] | AliasedClass[T]:
    if workspace_id is None:
        return published
    published_mapper = inspect(published)
    shadow_table = inspect(shadow).local_table
    # Every override masks its published row, including tombstones and rows
    # that will not match the caller's filters.
    override = (
        select(1)
        .select_from(shadow_table)
        .where(
            shadow_table.c.workspace_id == workspace_id,
            *(shadow_table.c[column.name] == column for column in published_mapper.primary_key),
        )
        .correlate(published_mapper.local_table)
        .exists()
    )
    columns = list(published_mapper.columns)
    combined = union_all(
        select(*columns).where(~override),
        select(*(shadow_table.c[column.name] for column in columns)).where(
            shadow_table.c.workspace_id == workspace_id, ~shadow_table.c.deleted
        ),
    ).subquery()
    return aliased(published, combined, adapt_on_names=True)


def workspace_read[*Ts](statement: Select[*Ts], workspace_id: UUID | None) -> Select[*Ts]:
    if workspace_id is None:
        return statement
    # Keep draft identities separate from published objects and refresh them
    # when a later read follows another staged change in the same session.
    return statement.execution_options(identity_token=workspace_id, populate_existing=True)
