import os
import uuid
from collections import Counter
from collections.abc import Generator
from time import monotonic, sleep
from uuid import UUID

import pytest
import redis
from celery.contrib.testing.worker import start_worker
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from src.filters.celery_app import app
from src.filters.compilers.python import PythonCompiler
from src.filters.data_types import BoolData, DataObj, LabelRefData, Schema
from src.filters.dispatch.celery import CeleryRunnerDispatcher
from src.filters.functions import Call, Compare, Extend, Get, LiteralFloat, ScoreOf, WordOf
from src.filters.models import GroupAssignment, Grouping, GroupingStatus, Instance, Workflow, WorkflowStatus
from src.filters.runners.python.annotation_runner import PythonAnnotationRunner
from src.filters.runners.python.filter_runner import PythonFilterRunner
from src.filters.runners.python.group_runner import PythonGroupRunner
from src.filters.runners.python.label_source_runner import PythonLabelSourceRunner
from src.filters.runners.python.map_runner import PythonMapRunner
from src.filters.schemas import (
    CreateFunctionDefinitionRequest,
    PythonAnnotationRequest,
    PythonFilterRequest,
    PythonGroupRequest,
    PythonLabelSourceRequest,
    PythonMapRequest,
)
from src.filters.service import (
    create_function_definition,
    run_annotation,
    run_filter,
    run_group,
    run_label_source,
    run_map,
)
from src.schemas import Model
from test_support.test_data.scenarios import DatabaseScenario

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def _dump(value: Model) -> dict[str, object]:
    return value.model_dump(mode="json", by_alias=True, exclude_computed_fields=True)


def _create_function(test_db: Session, name: str, function: Model) -> UUID:
    result = create_function_definition(
        test_db,
        CreateFunctionDefinitionRequest(
            namespace="redis-integration",
            function_name=name,
            function_definition=_dump(function),
        ),
    )
    return result.function_definition_id


def _wait_for_workflow(test_db: Session, workflow_id: UUID) -> Workflow:
    deadline = monotonic() + 15
    while monotonic() < deadline:
        test_db.expire_all()
        workflow = test_db.get(Workflow, workflow_id)
        assert workflow is not None
        if workflow.workflow_status in (WorkflowStatus.COMPLETE, WorkflowStatus.FAILED):
            assert workflow.workflow_status == WorkflowStatus.COMPLETE, workflow.workflow_message
            return workflow
        sleep(0.05)
    pytest.fail(f"Celery worker did not finish workflow {workflow_id} within 15 seconds.")


def _wait_for_grouping(test_db: Session, grouping_id: UUID) -> Grouping:
    deadline = monotonic() + 15
    while monotonic() < deadline:
        test_db.expire_all()
        grouping = test_db.get(Grouping, grouping_id)
        assert grouping is not None
        if grouping.grouping_status in (GroupingStatus.COMPLETE, GroupingStatus.FAILED):
            assert grouping.grouping_status == GroupingStatus.COMPLETE, grouping.grouping_message
            return grouping
        sleep(0.05)
    pytest.fail(f"Celery worker did not finish grouping {grouping_id} within 15 seconds.")


@pytest.fixture
def celery_worker(
    test_url: str,
    test_db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    import src.filters.worker.tasks as worker_tasks

    redis_host = os.getenv("TEST_REDIS_HOST", "test_redis")
    redis_port = int(os.getenv("TEST_REDIS_PORT", "6379"))
    broker_url = f"redis://{redis_host}:{redis_port}/14"
    queue_name = f"filter-tests-{uuid.uuid4().hex}"
    redis_client = redis.Redis(host=redis_host, port=redis_port, db=14)
    worker_engine = create_engine(test_url)
    worker_session = sessionmaker(autoflush=False, bind=worker_engine)
    compiler = PythonCompiler()

    redis_client.flushdb()
    monkeypatch.setitem(
        worker_tasks.runners,
        "python",
        {
            "annotation": PythonAnnotationRunner(worker_session),
            "filter": PythonFilterRunner(worker_session, compiler=compiler),
            "group": PythonGroupRunner(worker_session, compiler=compiler),
            "ls": PythonLabelSourceRunner(worker_session),
            "map": PythonMapRunner(worker_session, compiler=compiler),
        },
    )
    monkeypatch.setitem(app.conf, "broker_url", broker_url)
    monkeypatch.setitem(app.conf, "task_default_queue", queue_name)
    app.close()

    try:
        with start_worker(
            app,
            pool="solo",
            concurrency=1,
            queues=[queue_name],
            perform_ping_check=False,
            shutdown_timeout=10,
        ):
            yield
    finally:
        app.close()
        redis_client.flushdb()
        redis_client.close()
        worker_engine.dispose()


def test_user_pipeline_dispatches_every_runner_through_redis(
    test_db: Session,
    filter_scenario: DatabaseScenario,
    celery_worker: None,
) -> None:
    dispatcher = CeleryRunnerDispatcher()
    user = filter_scenario.users["owner"]
    label_group = filter_scenario.label_groups["labels"]

    source_result = run_label_source(
        test_db,
        user,
        dispatcher,
        PythonLabelSourceRequest(label_group_id=label_group.label_group_id, output_name="All labels"),
    )
    source = _wait_for_workflow(test_db, source_result.workflow.workflow_id)
    assert source_result.workflow.workflow_status == WorkflowStatus.PENDING
    assert _instance_count(test_db, source.workflow_id) == len(filter_scenario.labels)
    source_values = test_db.scalars(select(Instance.value).where(Instance.workflow_id == source.workflow_id)).all()
    source_chapter_ids = set()
    for raw_value in source_values:
        label = DataObj.model_validate(raw_value).fields["label"]
        assert isinstance(label, LabelRefData)
        source_chapter_ids.add(label.value.chapter_id)
    assert source_chapter_ids == {chapter.chapter_id for chapter in filter_scenario.chapters.values()}

    annotation_result = run_annotation(
        test_db,
        user,
        dispatcher,
        PythonAnnotationRequest(
            workflow_id=source.workflow_id,
            new_fields={"reviewed": {"type": "bool", "defaultValue": False}},
        ),
    )
    annotated = _wait_for_workflow(test_db, annotation_result.workflow.workflow_id)
    annotated_schema = Schema.model_validate(annotated.schema)
    assert annotated_schema.fields["reviewed"].mutable
    annotated_values = test_db.scalars(
        select(Instance.value).where(Instance.workflow_id == annotated.workflow_id)
    ).all()
    assert all(DataObj.model_validate(value).fields["reviewed"] == BoolData(value=False) for value in annotated_values)

    score = Call(
        input_schema=annotated_schema,
        function=ScoreOf(),
        arguments=(Get(field_name="label", type="labelRef"),),
    )
    low_score = Call(
        input_schema=annotated_schema,
        function=Compare(type="float", op="lt"),
        arguments=(score, LiteralFloat(value=0.6)),
    )
    filter_definition_id = _create_function(test_db, "low-score", low_score)
    filter_result = run_filter(
        test_db,
        user,
        dispatcher,
        PythonFilterRequest(
            source_workflow_id=annotated.workflow_id,
            function_definition_id=filter_definition_id,
            output_name="Low-score labels",
        ),
    )
    filtered = _wait_for_workflow(test_db, filter_result.workflow.workflow_id)
    assert _instance_count(test_db, filtered.workflow_id) == 9

    filtered_schema = Schema.model_validate(filtered.schema)
    word = Call(
        input_schema=filtered_schema,
        function=WordOf(),
        arguments=(Get(field_name="label", type="labelRef"),),
    )
    add_word = Extend(input_schema=filtered_schema, fields={"word": word})
    map_definition_id = _create_function(test_db, "add-word", add_word)
    map_result = run_map(
        test_db,
        user,
        dispatcher,
        PythonMapRequest(
            source_workflow_id=filtered.workflow_id,
            function_definition_id=map_definition_id,
            output_name="Low-score labels with words",
        ),
    )
    mapped = _wait_for_workflow(test_db, map_result.workflow.workflow_id)
    assert _instance_count(test_db, mapped.workflow_id) == 9

    group_definition_id = _create_function(test_db, "group-by-word", Get(field_name="word", type="string"))
    group_result = run_group(
        test_db,
        user,
        dispatcher,
        PythonGroupRequest(
            workflow_id=mapped.workflow_id,
            function_definition_id=group_definition_id,
        ),
    )
    grouping = _wait_for_grouping(test_db, group_result.grouping.grouping_id)
    assignments = test_db.scalars(
        select(GroupAssignment.function_value).where(GroupAssignment.grouping_id == grouping.grouping_id)
    ).all()
    assert Counter(assignments) == Counter({"traveler": 4, "world": 3, "test": 1, "city": 1})


def _instance_count(test_db: Session, workflow_id: UUID) -> int:
    return (
        test_db.scalar(select(func.count()).select_from(Instance).where(Instance.workflow_id == workflow_id)) or 0
    )
