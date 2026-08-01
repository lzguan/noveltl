from typing import Any

from sqlalchemy import Delete, Select, Update, and_, exists, select
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from src.auth.constants import UserType
from src.auth.models import User
from src.filters.models import Instance, Workflow, WorkflowLabelGroup, WorkflowNovel
from src.labels.models import LabelContributor
from src.novels.constants import Role
from src.novels.models import NovelContributor


def workflow_access_condition(
    current_user: User,
    workflow_type: type[Workflow] = Workflow,
) -> ColumnElement[bool]:
    """Build the non-admin access condition for a workflow.

    A workflow must have at least one associated novel. The user must be an
    owner or editor of every associated novel and a contributor to every
    associated label group.
    """
    workflow_novel = aliased(WorkflowNovel)
    novel_contributor = aliased(NovelContributor)
    workflow_label_group = aliased(WorkflowLabelGroup)
    label_contributor = aliased(LabelContributor)

    has_novel_scope = exists(
        select(1)
        .select_from(workflow_novel)
        .where(workflow_novel.workflow_id == workflow_type.workflow_id)
        .correlate(workflow_type)
    )

    can_access_novel = exists(
        select(1)
        .select_from(novel_contributor)
        .where(novel_contributor.novel_id == workflow_novel.novel_id)
        .where(novel_contributor.user_id == current_user.user_id)
        .where(novel_contributor.contributor_role.in_([Role.OWNER, Role.EDITOR]))
    ).correlate(workflow_novel)
    has_inaccessible_novel = exists(
        select(1)
        .select_from(workflow_novel)
        .where(workflow_novel.workflow_id == workflow_type.workflow_id)
        .where(~can_access_novel)
        .correlate(workflow_type)
    )

    can_access_label_group = exists(
        select(1)
        .select_from(label_contributor)
        .where(label_contributor.label_group_id == workflow_label_group.label_group_id)
        .where(label_contributor.user_id == current_user.user_id)
    ).correlate(workflow_label_group)
    has_inaccessible_label_group = exists(
        select(1)
        .select_from(workflow_label_group)
        .where(workflow_label_group.workflow_id == workflow_type.workflow_id)
        .where(~can_access_label_group)
        .correlate(workflow_type)
    )

    return and_(
        has_novel_scope,
        ~has_inaccessible_novel,
        ~has_inaccessible_label_group,
    )


def workflow_mod_access_select[T: Select[tuple[Any, ...]]](
    stmt: T,
    current_user: User,
    workflow_type: type[Workflow] = Workflow,
) -> T:
    """Restrict a workflow select to workflows accessible to the user."""
    if current_user.user_type == UserType.ADMIN:
        return stmt
    return stmt.where(workflow_access_condition(current_user, workflow_type))


def workflow_mod_access_update[T: Update](
    stmt: T,
    current_user: User,
    workflow_type: type[Workflow] = Workflow,
) -> T:
    """Restrict a workflow update to workflows accessible to the user."""
    if current_user.user_type == UserType.ADMIN:
        return stmt
    return stmt.where(workflow_access_condition(current_user, workflow_type))


def workflow_mod_access_delete[T: Delete](
    stmt: T,
    current_user: User,
    workflow_type: type[Workflow] = Workflow,
) -> T:
    """Restrict a workflow deletion to workflows accessible to the user."""
    if current_user.user_type == UserType.ADMIN:
        return stmt
    return stmt.where(workflow_access_condition(current_user, workflow_type))


def instance_mod_access_select[T: Select[tuple[Any, ...]]](
    stmt: T, current_user: User, instance_type: type[Instance] = Instance
) -> T:
    """Restrict an instance select to instances accessible to the user."""
    if current_user.user_type == UserType.ADMIN:
        return stmt
    wf_alias = aliased(Workflow)
    return stmt.where(
        exists(
            workflow_mod_access_select(
                select(1).select_from(wf_alias).where(wf_alias.workflow_id == instance_type.workflow_id),
                current_user,
                wf_alias,
            )
        )
    )
