import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from src.filters.data_types import (
    DataObj,
    Schema,
    StringData,
    StringField,
    TextSpan,
    TextSpanData,
    TextSpanField,
)
from src.filters.functions import Call, Get, TextOf
from src.filters.models import (
    FunctionDefinition,
    GroupAssignment,
    Grouping,
    GroupingStatus,
    Instance,
    Workflow,
    WorkflowStatus,
)
from src.filters.runners.python.group_runner import PythonGroupInput, PythonGroupRunner
from src.novels.models import ChapterContent
from src.schemas import Model

JOB_ID = uuid.UUID("32a2fd0f-9d99-4da3-81aa-d41e338ed9fd")


def _dump(value: Model) -> dict[str, object]:
    return value.model_dump(mode="json", by_alias=True, exclude_computed_fields=True)


def _create_string_grouping(
    db: Session,
    *,
    mutable: bool = False,
) -> tuple[Workflow, Grouping, list[Instance]]:
    schema = Schema(fields={"word": StringField(mutable=mutable)})
    workflow = Workflow(workflow_name="Grouping test", schema=_dump(schema))
    function = Get(field_name="word", type="string")
    function_definition = FunctionDefinition(
        namespace="test",
        function_name="word",
        function_definition=_dump(function),
    )
    db.add_all([workflow, function_definition])
    db.flush()

    instances = [
        Instance(
            workflow_id=workflow.workflow_id,
            value=_dump(DataObj(fields={"word": StringData(value=word)})),
        )
        for word in ("alpha", "beta", "alpha")
    ]
    grouping = Grouping(
        workflow_id=workflow.workflow_id,
        function_definition_id=function_definition.function_definition_id,
        job_id=JOB_ID,
    )
    db.add_all([*instances, grouping])
    db.commit()
    return workflow, grouping, instances


def test_group_runner_persists_raw_values_and_is_idempotent(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    _, grouping, _ = _create_string_grouping(test_db)
    runner = PythonGroupRunner(testing_session_local, batch_size=1)
    request = PythonGroupInput(grouping_id=grouping.grouping_id)

    runner.execute(JOB_ID, request)
    runner.execute(JOB_ID, request)

    test_db.expire_all()
    stored_grouping = test_db.get(Grouping, grouping.grouping_id)
    assert stored_grouping is not None
    assert stored_grouping.grouping_status == GroupingStatus.COMPLETE
    assignments = test_db.execute(
        select(GroupAssignment).where(GroupAssignment.grouping_id == grouping.grouping_id)
    ).scalars()
    assert sorted(assignment.function_value for assignment in assignments) == ["alpha", "alpha", "beta"]


def test_group_runner_preloads_text_dependencies(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
    sf_chapter_content: ChapterContent,
) -> None:
    schema = Schema(fields={"span": TextSpanField()})
    function = Call(
        input_schema=schema,
        function=TextOf(),
        arguments=(Get(field_name="span", type="textSpan"),),
    )
    workflow = Workflow(
        workflow_name="Text grouping",
        schema=_dump(schema),
        workflow_status=WorkflowStatus.COMPLETE,
    )
    function_definition = FunctionDefinition(
        namespace="test",
        function_name="text-group",
        function_definition=_dump(function),
    )
    test_db.add_all([workflow, function_definition])
    test_db.flush()
    instance = Instance(
        workflow_id=workflow.workflow_id,
        value=_dump(
            DataObj(
                fields={
                    "span": TextSpanData(
                        value=TextSpan(
                            start=0,
                            end=5,
                            chapter_content_id=sf_chapter_content.chapter_content_id,
                        )
                    )
                }
            )
        ),
    )
    grouping = Grouping(
        workflow_id=workflow.workflow_id,
        function_definition_id=function_definition.function_definition_id,
        job_id=JOB_ID,
    )
    test_db.add_all([instance, grouping])
    test_db.commit()

    PythonGroupRunner(testing_session_local).execute(
        JOB_ID,
        PythonGroupInput(grouping_id=grouping.grouping_id),
    )

    assignment = test_db.execute(
        select(GroupAssignment).where(GroupAssignment.grouping_id == grouping.grouping_id)
    ).scalar_one()
    assert assignment.function_value == "Hello"


def test_group_runner_resumes_from_cached_assignments(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    _, grouping, instances = _create_string_grouping(test_db)
    cached_instance = instances[0]
    test_db.add(
        GroupAssignment(
            grouping_id=grouping.grouping_id,
            instance_id=cached_instance.instance_id,
            function_value="alpha",
        )
    )
    test_db.commit()

    PythonGroupRunner(testing_session_local, batch_size=1).execute(
        JOB_ID,
        PythonGroupInput(grouping_id=grouping.grouping_id),
    )

    assignment_count = test_db.scalar(
        select(func.count())
        .select_from(GroupAssignment)
        .where(GroupAssignment.grouping_id == grouping.grouping_id)
    )
    assert assignment_count == 3
    cached_assignment = test_db.execute(
        select(GroupAssignment).where(
            GroupAssignment.grouping_id == grouping.grouping_id,
            GroupAssignment.instance_id == cached_instance.instance_id,
        )
    ).scalar_one()
    assert cached_assignment.function_value == "alpha"


def test_group_runner_rejects_mutable_dependencies(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    _, grouping, _ = _create_string_grouping(test_db, mutable=True)

    try:
        PythonGroupRunner(testing_session_local).execute(
            JOB_ID,
            PythonGroupInput(grouping_id=grouping.grouping_id),
        )
    except ValueError as exc:
        assert "mutable workflow fields" in str(exc)
    else:
        raise AssertionError("Expected mutable grouping dependency to be rejected.")

    test_db.expire_all()
    stored_grouping = test_db.get(Grouping, grouping.grouping_id)
    assert stored_grouping is not None
    assert stored_grouping.grouping_status == GroupingStatus.FAILED
    assert stored_grouping.grouping_message is not None


def test_group_runner_ignores_stale_job(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    _, grouping, _ = _create_string_grouping(test_db)

    PythonGroupRunner(testing_session_local).execute(
        uuid.UUID("c8837b42-ecbd-4828-96bb-774c2d9a0540"),
        PythonGroupInput(grouping_id=grouping.grouping_id),
    )

    test_db.expire_all()
    stored_grouping = test_db.get(Grouping, grouping.grouping_id)
    assert stored_grouping is not None
    assert stored_grouping.grouping_status == GroupingStatus.PENDING
    assignment_count = test_db.scalar(
        select(func.count())
        .select_from(GroupAssignment)
        .where(GroupAssignment.grouping_id == grouping.grouping_id)
    )
    assert assignment_count == 0
