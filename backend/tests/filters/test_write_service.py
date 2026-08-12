from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from src.filters.data_types import BoolField, Schema, StringField
from src.filters.exceptions import (
    FunctionAlreadyExistsException,
    FunctionNotFoundException,
    GroupingAlreadyExistsException,
    InvalidRunnerRequestException,
    RunnerEnqueueFailedException,
    WorkflowNotFoundException,
    WorkflowNotReadyException,
)
from src.filters.functions import Extend, Get, LiteralString
from src.filters.models import (
    FunctionDefinition,
    Grouping,
    GroupingStatus,
    Workflow,
    WorkflowLabelGroup,
    WorkflowNovel,
    WorkflowStatus,
)
from src.filters.runners.python.filter_runner import PythonFilterInput
from src.filters.runners.python.group_runner import PythonGroupInput, PythonGroupRunner
from src.filters.runners.python.label_source_runner import PythonLabelSourceInput
from src.filters.runners.python.map_runner import PythonMapInput
from src.filters.schemas import (
    CreateFunctionDefinitionRequest,
    PythonFilterRequest,
    PythonGroupRequest,
    PythonLabelSourceRequest,
    PythonMapRequest,
    RenameWorkflowRequest,
)
from src.filters.service import (
    create_function_definition,
    rename_workflow,
    run_filter,
    run_group,
    run_label_source,
    run_map,
)
from src.novels.constants import Role
from src.novels.models import NovelContributor
from src.schemas import Model
from test_support.filters import RecordingRunnerDispatcher
from test_support.test_data.scenarios import DatabaseScenario


def dump_model(value: Model) -> dict[str, object]:
    return value.model_dump(mode="json", by_alias=True, exclude_computed_fields=True)


def add_scoped_workflow(
    db: Session,
    scenario: DatabaseScenario,
    schema: Schema,
    *,
    status: WorkflowStatus = WorkflowStatus.COMPLETE,
) -> Workflow:
    workflow = Workflow(schema=dump_model(schema), workflow_status=status)
    db.add(workflow)
    db.flush()
    novel = scenario.novels["novel_1"]
    label_group = scenario.label_groups["official"]
    db.add_all(
        [
            WorkflowNovel(workflow_id=workflow.workflow_id, novel_id=novel.novel_id),
            WorkflowLabelGroup(
                workflow_id=workflow.workflow_id,
                label_group_id=label_group.label_group_id,
            ),
        ]
    )
    db.commit()
    return workflow


def add_function(db: Session, name: str, function: Model) -> FunctionDefinition:
    definition = FunctionDefinition(
        namespace="write-tests",
        function_name=name,
        function_definition=dump_model(function),
    )
    db.add(definition)
    db.commit()
    return definition


def test_create_function_definition_normalizes_and_detects_database_conflict(
    test_db: Session,
) -> None:
    request = CreateFunctionDefinitionRequest(
        namespace="  glossary  ",
        functionName="  constant-name  ",
        functionDefinition={"name": "literalString", "value": "Alice"},
    )

    created = create_function_definition(test_db, request)

    assert created.namespace == "glossary"
    assert created.function_name == "constant-name"
    assert created.function_definition == {"name": "literalString", "value": "Alice", "mutable": False}
    with pytest.raises(FunctionAlreadyExistsException):
        create_function_definition(test_db, request)


def test_rename_workflow_updates_only_accessible_workflow(
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    workflow = add_scoped_workflow(test_db, sample_scenario, Schema())
    admin = sample_scenario.users["admin"]

    renamed = rename_workflow(
        test_db,
        admin,
        workflow.workflow_id,
        RenameWorkflowRequest(workflowName="Review candidates"),
    )
    cleared = rename_workflow(
        test_db,
        admin,
        workflow.workflow_id,
        RenameWorkflowRequest(workflowName=None),
    )

    assert renamed.workflow_name == "Review candidates"
    assert cleared.workflow_name is None
    with pytest.raises(WorkflowNotFoundException):
        rename_workflow(
            test_db,
            sample_scenario.users["user"],
            workflow.workflow_id,
            RenameWorkflowRequest(workflowName="Hidden"),
        )


def test_label_source_commits_scope_before_dispatch_and_sends_exact_input(
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    label_group = sample_scenario.label_groups["official"]
    observed_workflow_ids = []

    def observe_commit(job_id, runner_input) -> None:
        assert isinstance(runner_input, PythonLabelSourceInput)
        with Session(test_db.get_bind()) as observer:
            workflow = observer.get(Workflow, runner_input.output_workflow_id)
            assert workflow is not None
            assert workflow.job_id == job_id
            assert workflow.workflow_status == WorkflowStatus.PENDING
            observed_workflow_ids.append(workflow.workflow_id)

    dispatcher = RecordingRunnerDispatcher(on_enqueue=observe_commit)
    result = run_label_source(
        test_db,
        sample_scenario.users["admin"],
        dispatcher,
        PythonLabelSourceRequest(labelGroupId=label_group.label_group_id, outputName="Labels"),
    )

    assert observed_workflow_ids == [result.workflow.workflow_id]
    assert result.workflow.novel_ids == [label_group.novel_id]
    assert result.workflow.label_group_ids == [label_group.label_group_id]
    assert dispatcher.jobs == [
        (
            result.job_id,
            PythonLabelSourceInput(
                runtime_name="python",
                runner_name="ls",
                label_group_id=label_group.label_group_id,
                output_workflow_id=result.workflow.workflow_id,
            ),
        )
    ]


def test_label_source_hides_inaccessible_group_and_does_not_dispatch(
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    dispatcher = RecordingRunnerDispatcher()
    with pytest.raises(WorkflowNotFoundException):
        run_label_source(
            test_db,
            sample_scenario.users["user"],
            dispatcher,
            PythonLabelSourceRequest(labelGroupId=sample_scenario.label_groups["official"].label_group_id),
        )
    assert dispatcher.jobs == []


def test_label_source_allows_novel_editor_with_label_group_view_access(
    test_db: Session,
    label_access_scenario: DatabaseScenario,
) -> None:
    actor = label_access_scenario.users["collaborator"]
    label_group = label_access_scenario.label_groups["with_viewer"]
    test_db.add(
        NovelContributor(
            novel_id=label_group.novel_id,
            user_id=actor.user_id,
            contributor_role=Role.EDITOR,
        )
    )
    test_db.commit()
    dispatcher = RecordingRunnerDispatcher()

    result = run_label_source(
        test_db,
        actor,
        dispatcher,
        PythonLabelSourceRequest(labelGroupId=label_group.label_group_id),
    )

    assert result.workflow.novel_ids == [label_group.novel_id]
    assert result.workflow.label_group_ids == [label_group.label_group_id]
    assert len(dispatcher.jobs) == 1


def test_map_filter_and_group_create_correct_targets_and_payloads(
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    source_schema = Schema(fields={"name": StringField(), "active": BoolField()})
    map_source = add_scoped_workflow(test_db, sample_scenario, source_schema)
    filter_source = add_scoped_workflow(test_db, sample_scenario, source_schema)
    group_source = add_scoped_workflow(test_db, sample_scenario, source_schema)
    map_definition = add_function(
        test_db,
        "map",
        Extend(
            input_schema=source_schema,
            fields={"category": LiteralString(value="character")},
        ),
    )
    filter_definition = add_function(test_db, "filter", Get(field_name="active", type="bool"))
    group_definition = add_function(test_db, "group", Get(field_name="name", type="string"))
    dispatcher = RecordingRunnerDispatcher()
    admin = sample_scenario.users["admin"]

    mapped = run_map(
        test_db,
        admin,
        dispatcher,
        PythonMapRequest(
            sourceWorkflowId=map_source.workflow_id,
            functionDefinitionId=map_definition.function_definition_id,
            outputName="Mapped",
        ),
    )
    filtered = run_filter(
        test_db,
        admin,
        dispatcher,
        PythonFilterRequest(
            sourceWorkflowId=filter_source.workflow_id,
            functionDefinitionId=filter_definition.function_definition_id,
            outputName="Filtered",
        ),
    )
    grouped = run_group(
        test_db,
        admin,
        dispatcher,
        PythonGroupRequest(
            workflowId=group_source.workflow_id,
            functionDefinitionId=group_definition.function_definition_id,
        ),
    )

    assert set(mapped.workflow.workflow_schema.fields) == {"name", "active", "category"}
    assert filtered.workflow.workflow_schema == source_schema
    assert mapped.workflow.novel_ids == filtered.workflow.novel_ids
    assert mapped.workflow.label_group_ids == filtered.workflow.label_group_ids
    assert grouped.grouping.output_type == "string"
    assert len(dispatcher.jobs) == 3
    map_job, filter_job, group_job = dispatcher.jobs
    assert map_job[0] == mapped.job_id
    assert isinstance(map_job[1], PythonMapInput)
    assert map_job[1].source_workflow_id == map_source.workflow_id
    assert map_job[1].output_workflow_id == mapped.workflow.workflow_id
    assert filter_job[0] == filtered.job_id
    assert isinstance(filter_job[1], PythonFilterInput)
    assert filter_job[1].output_workflow_id == filtered.workflow.workflow_id
    assert group_job[0] == grouped.job_id
    assert group_job[1] == PythonGroupInput(
        runtime_name="python",
        runner_name="group",
        grouping_id=grouped.grouping.grouping_id,
    )


def test_runner_validation_happens_before_target_creation_or_dispatch(
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    source = add_scoped_workflow(
        test_db,
        sample_scenario,
        Schema(fields={"name": StringField()}),
    )
    invalid_filter = add_function(test_db, "not-bool", Get(field_name="name", type="string"))
    dispatcher = RecordingRunnerDispatcher()

    with pytest.raises(InvalidRunnerRequestException, match="return a boolean"):
        run_filter(
            test_db,
            sample_scenario.users["admin"],
            dispatcher,
            PythonFilterRequest(
                sourceWorkflowId=source.workflow_id,
                functionDefinitionId=invalid_filter.function_definition_id,
            ),
        )

    assert dispatcher.jobs == []
    output_count = test_db.scalar(
        select(func.count()).select_from(Workflow).where(Workflow.workflow_id != source.workflow_id)
    )
    assert output_count == 0


def test_incomplete_or_missing_sources_do_not_dispatch(
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    source_schema = Schema(fields={"name": StringField()})
    source = add_scoped_workflow(
        test_db,
        sample_scenario,
        source_schema,
        status=WorkflowStatus.PENDING,
    )
    function = add_function(
        test_db,
        "map-pending",
        Extend(input_schema=source_schema, fields={"extra": LiteralString(value="x")}),
    )
    dispatcher = RecordingRunnerDispatcher()
    admin = sample_scenario.users["admin"]

    with pytest.raises(WorkflowNotReadyException):
        run_map(
            test_db,
            admin,
            dispatcher,
            PythonMapRequest(
                sourceWorkflowId=source.workflow_id,
                functionDefinitionId=function.function_definition_id,
            ),
        )
    with pytest.raises(FunctionNotFoundException):
        run_map(
            test_db,
            admin,
            dispatcher,
            PythonMapRequest(
                sourceWorkflowId=add_scoped_workflow(test_db, sample_scenario, source_schema).workflow_id,
                functionDefinitionId=uuid4(),
            ),
        )
    assert dispatcher.jobs == []


def test_grouping_duplicate_is_reported_as_domain_conflict(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
    sample_scenario: DatabaseScenario,
) -> None:
    workflow = add_scoped_workflow(
        test_db,
        sample_scenario,
        Schema(fields={"name": StringField()}),
    )
    function = add_function(test_db, "duplicate-group", Get(field_name="name", type="string"))
    request = PythonGroupRequest(
        workflowId=workflow.workflow_id,
        functionDefinitionId=function.function_definition_id,
    )

    first = run_group(test_db, sample_scenario.users["admin"], RecordingRunnerDispatcher(), request)
    PythonGroupRunner(testing_session_local).execute(
        first.job_id,
        PythonGroupInput(
            runtime_name="python",
            runner_name="group",
            grouping_id=first.grouping.grouping_id,
        ),
    )
    test_db.expire_all()
    with pytest.raises(GroupingAlreadyExistsException):
        run_group(test_db, sample_scenario.users["admin"], RecordingRunnerDispatcher(), request)


@pytest.mark.parametrize("operation", ["workflow", "grouping"])
def test_enqueue_failure_marks_committed_target_failed(
    operation: str,
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    dispatcher = RecordingRunnerDispatcher(enqueue_error=RunnerEnqueueFailedException("broker unavailable"))
    admin = sample_scenario.users["admin"]

    if operation == "workflow":
        label_group = sample_scenario.label_groups["official"]
        with pytest.raises(RunnerEnqueueFailedException):
            run_label_source(
                test_db,
                admin,
                dispatcher,
                PythonLabelSourceRequest(labelGroupId=label_group.label_group_id, outputName="Failed"),
            )
        target = test_db.execute(select(Workflow).where(Workflow.workflow_name == "Failed")).scalar_one()
        assert target.workflow_status == WorkflowStatus.FAILED
        assert target.workflow_message == "Runner publication failed."
    else:
        workflow = add_scoped_workflow(
            test_db,
            sample_scenario,
            Schema(fields={"name": StringField()}),
        )
        function = add_function(test_db, "failed-group", Get(field_name="name", type="string"))
        with pytest.raises(RunnerEnqueueFailedException):
            run_group(
                test_db,
                admin,
                dispatcher,
                PythonGroupRequest(
                    workflowId=workflow.workflow_id,
                    functionDefinitionId=function.function_definition_id,
                ),
            )
        target = test_db.execute(select(Grouping).where(Grouping.workflow_id == workflow.workflow_id)).scalar_one()
        assert target.grouping_status == GroupingStatus.FAILED
        assert target.grouping_message == "Runner publication failed."
        test_db.refresh(workflow)
        assert workflow.workflow_status == WorkflowStatus.FAILED
        assert workflow.workflow_message == "Runner publication failed."
