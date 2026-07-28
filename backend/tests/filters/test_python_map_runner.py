import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from src.filters.data_types import (
    DataObj,
    IntField,
    Schema,
    StringData,
    StringField,
    TextSpan,
    TextSpanData,
    TextSpanField,
)
from src.filters.functions import Call, Construct, FunctionType, Get, Rename, RenamePair, TextAround
from src.filters.models import FunctionDefinition, Instance, Workflow, WorkflowStatus
from src.filters.runners.python.map_runner import PythonMapInput, PythonMapRunner
from src.novels.models import ChapterContent
from src.schemas import Model

JOB_ID = uuid.UUID("78c9409e-c9ec-4f3b-9c70-f0eec979d88e")
STALE_JOB_ID = uuid.UUID("46fd62a2-bc62-40da-bda6-f521336188a9")


def _dump(value: Model) -> dict[str, object]:
    return value.model_dump(mode="json", by_alias=True, exclude_computed_fields=True)


def _create_map_case(
    db: Session,
    *,
    words: tuple[str, ...] = ("alpha", "beta", "gamma"),
    source_status: WorkflowStatus = WorkflowStatus.COMPLETE,
    function: FunctionType | None = None,
    output_schema: Schema | None = None,
) -> tuple[Workflow, Workflow, FunctionDefinition, list[Instance]]:
    source_schema = Schema(fields={"word": StringField()})
    function = function or Rename(
        original_schema=source_schema,
        rename_pairs=(RenamePair(old_name="word", new_name="term"),),
    )
    if output_schema is None:
        assert isinstance(function.signature.output, Schema)
        output_schema = function.signature.output

    source = Workflow(
        workflow_name="Map source",
        schema=_dump(source_schema),
        workflow_status=source_status,
    )
    output = Workflow(
        workflow_name="Map output",
        schema=_dump(output_schema),
        job_id=JOB_ID,
    )
    function_definition = FunctionDefinition(
        namespace="test",
        function_name="map-function",
        function_definition=_dump(function),
    )
    db.add_all([source, output, function_definition])
    db.flush()

    instances = [
        Instance(
            instance_id=uuid.UUID(int=index),
            workflow_id=source.workflow_id,
            value=_dump(DataObj(fields={"word": StringData(value=word)})),
        )
        for index, word in enumerate(words, start=1)
    ]
    db.add_all(instances)
    db.commit()
    return source, output, function_definition, instances


def _map_input(
    source: Workflow,
    output: Workflow,
    function_definition: FunctionDefinition,
) -> PythonMapInput:
    return PythonMapInput(
        source_workflow_id=source.workflow_id,
        output_workflow_id=output.workflow_id,
        function_definition_id=function_definition.function_definition_id,
    )


def test_map_runner_maps_in_bounded_batches_and_is_idempotent(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    source, output, function_definition, _ = _create_map_case(test_db)
    request = _map_input(source, output, function_definition)
    runner = PythonMapRunner(testing_session_local, batch_size=1)

    runner.execute(JOB_ID, request)
    runner.execute(JOB_ID, request)

    test_db.expire_all()
    stored_output = test_db.get(Workflow, output.workflow_id)
    assert stored_output is not None
    assert stored_output.workflow_status == WorkflowStatus.COMPLETE
    values = test_db.execute(select(Instance.value).where(Instance.workflow_id == output.workflow_id)).scalars()
    parsed = [DataObj.model_validate(value) for value in values]
    mapped_words: list[str] = []
    for instance in parsed:
        term = instance.fields["term"]
        assert isinstance(term, StringData)
        mapped_words.append(term.value)
    assert sorted(mapped_words) == ["alpha", "beta", "gamma"]


def test_map_runner_preloads_text_dependencies(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
    sf_chapter_content: ChapterContent,
) -> None:
    source_schema = Schema(fields={"span": TextSpanField()})
    text_around = Call(
        input_schema=source_schema,
        function=TextAround(slack=1),
        arguments=(Get(field_name="span", type="textSpan"),),
    )
    function = Construct(
        input_schema=source_schema,
        fields={"text": text_around},
    )
    output_schema = function.signature.output
    assert isinstance(output_schema, Schema)

    source = Workflow(
        workflow_name="Text map source",
        schema=_dump(source_schema),
        workflow_status=WorkflowStatus.COMPLETE,
    )
    output = Workflow(
        workflow_name="Text map output",
        schema=_dump(output_schema),
        job_id=JOB_ID,
    )
    function_definition = FunctionDefinition(
        namespace="test",
        function_name="text-map",
        function_definition=_dump(function),
    )
    test_db.add_all([source, output, function_definition])
    test_db.flush()
    test_db.add(
        Instance(
            workflow_id=source.workflow_id,
            value=_dump(
                DataObj(
                    fields={
                        "span": TextSpanData(
                            value=TextSpan(
                                start=6,
                                end=11,
                                chapter_content_id=sf_chapter_content.chapter_content_id,
                            )
                        )
                    }
                )
            ),
        )
    )
    test_db.commit()

    PythonMapRunner(testing_session_local).execute(
        JOB_ID,
        _map_input(source, output, function_definition),
    )

    raw_output = test_db.execute(select(Instance.value).where(Instance.workflow_id == output.workflow_id)).scalar_one()
    mapped = DataObj.model_validate(raw_output)
    assert mapped.fields["text"] == StringData(value=" world.")


def test_map_runner_completes_empty_source(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    source, output, function_definition, _ = _create_map_case(test_db, words=())

    PythonMapRunner(testing_session_local).execute(
        JOB_ID,
        _map_input(source, output, function_definition),
    )

    test_db.expire_all()
    stored_output = test_db.get(Workflow, output.workflow_id)
    assert stored_output is not None
    assert stored_output.workflow_status == WorkflowStatus.COMPLETE
    assert (
        test_db.scalar(select(func.count()).select_from(Instance).where(Instance.workflow_id == output.workflow_id))
        == 0
    )


def test_map_runner_ignores_stale_job(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    source, output, function_definition, _ = _create_map_case(test_db)

    PythonMapRunner(testing_session_local).execute(
        STALE_JOB_ID,
        _map_input(source, output, function_definition),
    )

    test_db.expire_all()
    stored_output = test_db.get(Workflow, output.workflow_id)
    assert stored_output is not None
    assert stored_output.workflow_status == WorkflowStatus.PENDING
    assert (
        test_db.scalar(select(func.count()).select_from(Instance).where(Instance.workflow_id == output.workflow_id))
        == 0
    )


def test_map_runner_rejects_incomplete_source(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    source, output, function_definition, _ = _create_map_case(
        test_db,
        source_status=WorkflowStatus.PENDING,
    )

    with pytest.raises(ValueError, match="Source workflow must be complete"):
        PythonMapRunner(testing_session_local).execute(
            JOB_ID,
            _map_input(source, output, function_definition),
        )

    test_db.expire_all()
    stored_output = test_db.get(Workflow, output.workflow_id)
    assert stored_output is not None
    assert stored_output.workflow_status == WorkflowStatus.FAILED


def test_map_runner_rejects_same_source_and_output(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    schema = Schema(fields={"word": StringField()})
    workflow = Workflow(
        workflow_name="Self map",
        schema=_dump(schema),
        job_id=JOB_ID,
    )
    function = Rename(
        original_schema=schema,
        rename_pairs=(RenamePair(old_name="word", new_name="term"),),
    )
    function_definition = FunctionDefinition(
        namespace="test",
        function_name="self-map",
        function_definition=_dump(function),
    )
    test_db.add_all([workflow, function_definition])
    test_db.commit()

    with pytest.raises(ValueError, match="must be distinct"):
        PythonMapRunner(testing_session_local).execute(
            JOB_ID,
            PythonMapInput(
                source_workflow_id=workflow.workflow_id,
                output_workflow_id=workflow.workflow_id,
                function_definition_id=function_definition.function_definition_id,
            ),
        )


def test_map_runner_rejects_incompatible_input_schema(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    required_schema = Schema(fields={"count": IntField()})
    function = Rename(
        original_schema=required_schema,
        rename_pairs=(RenamePair(old_name="count", new_name="total"),),
    )
    source, output, function_definition, _ = _create_map_case(test_db, function=function)

    with pytest.raises(ValueError, match="does not satisfy"):
        PythonMapRunner(testing_session_local).execute(
            JOB_ID,
            _map_input(source, output, function_definition),
        )


def test_map_runner_rejects_scalar_output(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    function = Get(field_name="word", type="string")
    source, output, function_definition, _ = _create_map_case(
        test_db,
        function=function,
        output_schema=Schema(fields={"word": StringField()}),
    )

    with pytest.raises(ValueError, match="must return an object schema"):
        PythonMapRunner(testing_session_local).execute(
            JOB_ID,
            _map_input(source, output, function_definition),
        )


def test_map_runner_rejects_mismatched_output_schema(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    source, output, function_definition, _ = _create_map_case(
        test_db,
        output_schema=Schema(fields={"word": StringField()}),
    )

    with pytest.raises(ValueError, match="does not match"):
        PythonMapRunner(testing_session_local).execute(
            JOB_ID,
            _map_input(source, output, function_definition),
        )


def test_map_runner_rejects_nonempty_output(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    source, output, function_definition, _ = _create_map_case(test_db)
    test_db.add(
        Instance(
            workflow_id=output.workflow_id,
            value=_dump(DataObj(fields={"term": StringData(value="existing")})),
        )
    )
    test_db.commit()

    with pytest.raises(ValueError, match="must be empty"):
        PythonMapRunner(testing_session_local).execute(
            JOB_ID,
            _map_input(source, output, function_definition),
        )


def test_map_runner_preserves_committed_batches_on_terminal_failure(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    source, output, function_definition, instances = _create_map_case(test_db)
    instances[1].value = {"invalid": True}
    test_db.commit()
    request = _map_input(source, output, function_definition)
    runner = PythonMapRunner(testing_session_local, batch_size=1)

    with pytest.raises(ValueError):
        runner.execute(JOB_ID, request)

    test_db.expire_all()
    stored_output = test_db.get(Workflow, output.workflow_id)
    assert stored_output is not None
    assert stored_output.workflow_status == WorkflowStatus.FAILED
    assert stored_output.workflow_message is not None
    output_count = test_db.scalar(
        select(func.count()).select_from(Instance).where(Instance.workflow_id == output.workflow_id)
    )
    assert output_count == 1

    runner.execute(JOB_ID, request)
    assert (
        test_db.scalar(select(func.count()).select_from(Instance).where(Instance.workflow_id == output.workflow_id))
        == 1
    )
