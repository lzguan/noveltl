from collections.abc import Iterable

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, aliased

from src.filters.functions import Get
from src.filters.models import FunctionDefinition, Grouping, Workflow, WorkflowLabelGroup, WorkflowNovel
from src.filters.permissions import (
    grouping_mod_access_select,
    workflow_mod_access_delete,
    workflow_mod_access_select,
    workflow_mod_access_update,
)
from src.labels.models import LabelGroup
from src.novels.constants import Role
from src.novels.models import Novel, NovelContributor
from test_support.test_data.scenarios import DatabaseScenario


def add_workflow(
    db: Session,
    *,
    novels: Iterable[Novel] = (),
    label_groups: Iterable[LabelGroup] = (),
) -> Workflow:
    workflow = Workflow(workflow_name="Permission test", schema={"fields": {}})
    db.add(workflow)
    db.flush()
    db.add_all(WorkflowNovel(workflow_id=workflow.workflow_id, novel_id=novel.novel_id) for novel in novels)
    db.add_all(
        WorkflowLabelGroup(
            workflow_id=workflow.workflow_id,
            label_group_id=label_group.label_group_id,
        )
        for label_group in label_groups
    )
    db.commit()
    return workflow


def add_novel_contributor(
    db: Session,
    scenario: DatabaseScenario,
    *,
    user: str,
    novel: str,
    role: Role,
) -> None:
    db.add(
        NovelContributor(
            novel_id=scenario.novels[novel].novel_id,
            user_id=scenario.users[user].user_id,
            contributor_role=role,
        )
    )
    db.commit()


def select_workflow(
    db: Session,
    scenario: DatabaseScenario,
    workflow: Workflow,
    user: str,
) -> Workflow | None:
    stmt = select(Workflow).where(Workflow.workflow_id == workflow.workflow_id)
    stmt = workflow_mod_access_select(stmt, scenario.users[user])
    return db.execute(stmt).scalar_one_or_none()


def add_grouping(db: Session, workflow: Workflow) -> Grouping:
    function_definition = FunctionDefinition(
        namespace="permissions",
        function_name=f"group-{workflow.workflow_id}",
        function_definition=Get(field_name="value", type="string").model_dump(
            mode="json", by_alias=True, exclude_computed_fields=True
        ),
    )
    db.add(function_definition)
    db.flush()
    grouping = Grouping(
        workflow_id=workflow.workflow_id,
        function_definition_id=function_definition.function_definition_id,
    )
    db.add(grouping)
    db.commit()
    return grouping


class TestWorkflowSelectPermissions:
    def test_novel_owner_and_label_group_owner_can_select(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        workflow = add_workflow(
            test_db,
            novels=[label_access_scenario.novels["public"]],
            label_groups=[label_access_scenario.label_groups["owner_only"]],
        )

        assert select_workflow(test_db, label_access_scenario, workflow, "owner") is not None

    def test_novel_editor_and_label_group_viewer_can_select(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        add_novel_contributor(
            test_db,
            label_access_scenario,
            user="collaborator",
            novel="public",
            role=Role.EDITOR,
        )
        workflow = add_workflow(
            test_db,
            novels=[label_access_scenario.novels["public"]],
            label_groups=[label_access_scenario.label_groups["with_viewer"]],
        )

        assert select_workflow(test_db, label_access_scenario, workflow, "collaborator") is not None

    def test_novel_viewer_cannot_select(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        add_novel_contributor(
            test_db,
            label_access_scenario,
            user="collaborator",
            novel="public",
            role=Role.VIEWER,
        )
        workflow = add_workflow(
            test_db,
            novels=[label_access_scenario.novels["public"]],
            label_groups=[label_access_scenario.label_groups["with_viewer"]],
        )

        assert select_workflow(test_db, label_access_scenario, workflow, "collaborator") is None

    def test_missing_label_group_access_denies_select(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        add_novel_contributor(
            test_db,
            label_access_scenario,
            user="collaborator",
            novel="public",
            role=Role.EDITOR,
        )
        workflow = add_workflow(
            test_db,
            novels=[label_access_scenario.novels["public"]],
            label_groups=[label_access_scenario.label_groups["owner_only"]],
        )

        assert select_workflow(test_db, label_access_scenario, workflow, "collaborator") is None

    def test_access_is_required_for_every_associated_novel(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        add_novel_contributor(
            test_db,
            label_access_scenario,
            user="collaborator",
            novel="public",
            role=Role.EDITOR,
        )
        workflow = add_workflow(
            test_db,
            novels=[
                label_access_scenario.novels["public"],
                label_access_scenario.novels["private"],
            ],
            label_groups=[label_access_scenario.label_groups["with_editor"]],
        )

        assert select_workflow(test_db, label_access_scenario, workflow, "collaborator") is None

    def test_unscoped_workflow_is_denied(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        workflow = add_workflow(test_db)

        assert select_workflow(test_db, label_access_scenario, workflow, "owner") is None

    def test_admin_bypasses_scope_checks(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        workflow = add_workflow(test_db)

        assert select_workflow(test_db, label_access_scenario, workflow, "admin") is not None

    def test_select_supports_workflow_alias(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        workflow = add_workflow(
            test_db,
            novels=[label_access_scenario.novels["public"]],
            label_groups=[label_access_scenario.label_groups["owner_only"]],
        )
        workflow_alias = aliased(Workflow)
        stmt = select(workflow_alias).where(workflow_alias.workflow_id == workflow.workflow_id)
        stmt = workflow_mod_access_select(
            stmt,
            label_access_scenario.users["owner"],
            workflow_alias,
        )

        assert test_db.execute(stmt).scalar_one_or_none() is not None


class TestWorkflowMutationPermissions:
    def test_owner_can_update(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        workflow = add_workflow(
            test_db,
            novels=[label_access_scenario.novels["public"]],
            label_groups=[label_access_scenario.label_groups["owner_only"]],
        )
        stmt = (
            update(Workflow)
            .where(Workflow.workflow_id == workflow.workflow_id)
            .values(workflow_name="Updated")
            .returning(Workflow.workflow_id)
        )
        stmt = workflow_mod_access_update(stmt, label_access_scenario.users["owner"])

        assert test_db.execute(stmt).scalar_one_or_none() == workflow.workflow_id

    def test_novel_viewer_cannot_update(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        add_novel_contributor(
            test_db,
            label_access_scenario,
            user="collaborator",
            novel="public",
            role=Role.VIEWER,
        )
        workflow = add_workflow(
            test_db,
            novels=[label_access_scenario.novels["public"]],
            label_groups=[label_access_scenario.label_groups["with_viewer"]],
        )
        stmt = (
            update(Workflow)
            .where(Workflow.workflow_id == workflow.workflow_id)
            .values(workflow_name="Denied")
            .returning(Workflow.workflow_id)
        )
        stmt = workflow_mod_access_update(stmt, label_access_scenario.users["collaborator"])

        assert test_db.execute(stmt).scalar_one_or_none() is None

    def test_novel_viewer_cannot_delete(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        add_novel_contributor(
            test_db,
            label_access_scenario,
            user="collaborator",
            novel="public",
            role=Role.VIEWER,
        )
        workflow = add_workflow(
            test_db,
            novels=[label_access_scenario.novels["public"]],
            label_groups=[label_access_scenario.label_groups["with_viewer"]],
        )
        stmt = delete(Workflow).where(Workflow.workflow_id == workflow.workflow_id)
        stmt = workflow_mod_access_delete(stmt, label_access_scenario.users["collaborator"])

        test_db.execute(stmt)
        assert test_db.get(Workflow, workflow.workflow_id) is not None


class TestGroupingSelectPermissions:
    def test_grouping_inherits_accessible_workflow_scope(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        workflow = add_workflow(
            test_db,
            novels=[label_access_scenario.novels["public"]],
            label_groups=[label_access_scenario.label_groups["owner_only"]],
        )
        grouping = add_grouping(test_db, workflow)
        statement = grouping_mod_access_select(
            select(Grouping).where(Grouping.grouping_id == grouping.grouping_id),
            label_access_scenario.users["owner"],
        )

        assert test_db.execute(statement).scalar_one_or_none() is not None

    def test_grouping_hides_inaccessible_workflow_scope(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        workflow = add_workflow(
            test_db,
            novels=[label_access_scenario.novels["public"]],
            label_groups=[label_access_scenario.label_groups["owner_only"]],
        )
        grouping = add_grouping(test_db, workflow)
        statement = grouping_mod_access_select(
            select(Grouping).where(Grouping.grouping_id == grouping.grouping_id),
            label_access_scenario.users["collaborator"],
        )

        assert test_db.execute(statement).scalar_one_or_none() is None
