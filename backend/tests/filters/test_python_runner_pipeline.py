import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from src.filters.data_types import Schema
from src.filters.functions import (
    Call,
    Compare,
    Extend,
    Get,
    LiteralFloat,
    Rename,
    RenamePair,
    ScoreOf,
    WordOf,
)
from src.filters.models import (
    FunctionDefinition,
    GroupAssignment,
    Grouping,
    GroupingStatus,
    Instance,
    Workflow,
)
from src.filters.runners.python.filter_runner import PythonFilterInput, PythonFilterRunner
from src.filters.runners.python.group_runner import PythonGroupInput, PythonGroupRunner
from src.filters.runners.python.label_source_runner import (
    LABEL_SOURCE_SCHEMA,
    PythonLabelSourceInput,
    PythonLabelSourceRunner,
)
from src.filters.runners.python.map_runner import PythonMapInput, PythonMapRunner
from src.labels.models import Label
from src.schemas import Model
from test_support.test_data.scenarios import DatabaseScenario

SOURCE_JOB_ID = uuid.UUID("b3cbf911-bb1b-4787-9bff-afbc83b53ad8")
FILTER_JOB_ID = uuid.UUID("ab694f0d-55d3-424a-a298-9e42c283b42c")
WORD_MAP_JOB_ID = uuid.UUID("e60f1d46-a109-47d6-9aca-5efead558a67")
RENAME_MAP_JOB_ID = uuid.UUID("c69a315e-4637-4d76-a288-c1b58242f580")
GROUP_JOB_ID = uuid.UUID("8c08b509-8536-4323-b898-46bcd00388d1")


def _dump(value: Model) -> dict[str, object]:
    return value.model_dump(mode="json", by_alias=True, exclude_computed_fields=True)


def _run_pipeline(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
    label_group_id: uuid.UUID,
    score_threshold: float,
) -> tuple[int, int, list[str | int | bool]]:
    score = Call(
        input_schema=LABEL_SOURCE_SCHEMA,
        function=ScoreOf(),
        arguments=(Get(field_name="label", type="labelRef"),),
    )
    bad_score = Call(
        input_schema=LABEL_SOURCE_SCHEMA,
        function=Compare(type="float", op="lt"),
        arguments=(score, LiteralFloat(value=score_threshold)),
    )
    word = Call(
        input_schema=LABEL_SOURCE_SCHEMA,
        function=WordOf(),
        arguments=(Get(field_name="label", type="labelRef"),),
    )
    add_word = Extend(
        input_schema=LABEL_SOURCE_SCHEMA,
        fields={"word": word},
    )
    word_schema = add_word.signature.output
    assert isinstance(word_schema, Schema)
    rename_word = Rename(
        original_schema=word_schema,
        rename_pairs=(RenamePair(old_name="word", new_name="term"),),
    )
    renamed_schema = rename_word.signature.output
    assert isinstance(renamed_schema, Schema)
    group_by_term = Get(field_name="term", type="string")

    source_workflow = Workflow(
        workflow_name="All labels",
        schema=_dump(LABEL_SOURCE_SCHEMA),
        job_id=SOURCE_JOB_ID,
    )
    filtered_workflow = Workflow(
        workflow_name="Bad-score labels",
        schema=_dump(LABEL_SOURCE_SCHEMA),
        job_id=FILTER_JOB_ID,
    )
    word_workflow = Workflow(
        workflow_name="Labels with words",
        schema=_dump(word_schema),
        job_id=WORD_MAP_JOB_ID,
    )
    renamed_workflow = Workflow(
        workflow_name="Labels with terms",
        schema=_dump(renamed_schema),
        job_id=RENAME_MAP_JOB_ID,
    )
    score_definition = FunctionDefinition(
        namespace="pipeline",
        function_name="bad-score",
        function_definition=_dump(bad_score),
    )
    word_definition = FunctionDefinition(
        namespace="pipeline",
        function_name="add-word",
        function_definition=_dump(add_word),
    )
    rename_definition = FunctionDefinition(
        namespace="pipeline",
        function_name="rename-word",
        function_definition=_dump(rename_word),
    )
    group_definition = FunctionDefinition(
        namespace="pipeline",
        function_name="group-by-term",
        function_definition=_dump(group_by_term),
    )
    test_db.add_all(
        [
            source_workflow,
            filtered_workflow,
            word_workflow,
            renamed_workflow,
            score_definition,
            word_definition,
            rename_definition,
            group_definition,
        ]
    )
    test_db.flush()
    grouping = Grouping(
        workflow_id=renamed_workflow.workflow_id,
        function_definition_id=group_definition.function_definition_id,
        job_id=GROUP_JOB_ID,
    )
    test_db.add(grouping)
    test_db.commit()

    PythonLabelSourceRunner(testing_session_local, batch_size=1).execute(
        SOURCE_JOB_ID,
        PythonLabelSourceInput(
            label_group_id=label_group_id,
            output_workflow_id=source_workflow.workflow_id,
        ),
    )
    PythonFilterRunner(testing_session_local, batch_size=1).execute(
        FILTER_JOB_ID,
        PythonFilterInput(
            source_workflow_id=source_workflow.workflow_id,
            output_workflow_id=filtered_workflow.workflow_id,
            function_definition_id=score_definition.function_definition_id,
        ),
    )
    PythonMapRunner(testing_session_local, batch_size=1).execute(
        WORD_MAP_JOB_ID,
        PythonMapInput(
            source_workflow_id=filtered_workflow.workflow_id,
            output_workflow_id=word_workflow.workflow_id,
            function_definition_id=word_definition.function_definition_id,
        ),
    )
    PythonMapRunner(testing_session_local, batch_size=1).execute(
        RENAME_MAP_JOB_ID,
        PythonMapInput(
            source_workflow_id=word_workflow.workflow_id,
            output_workflow_id=renamed_workflow.workflow_id,
            function_definition_id=rename_definition.function_definition_id,
        ),
    )
    PythonGroupRunner(testing_session_local, batch_size=1).execute(
        GROUP_JOB_ID,
        PythonGroupInput(grouping_id=grouping.grouping_id),
    )

    test_db.expire_all()
    stored_grouping = test_db.get(Grouping, grouping.grouping_id)
    assert stored_grouping is not None
    assert stored_grouping.grouping_status == GroupingStatus.COMPLETE

    source_count = (
        test_db.scalar(
            select(func.count()).select_from(Instance).where(Instance.workflow_id == source_workflow.workflow_id)
        )
        or 0
    )
    filtered_count = (
        test_db.scalar(
            select(func.count()).select_from(Instance).where(Instance.workflow_id == filtered_workflow.workflow_id)
        )
        or 0
    )
    assignments = list(
        test_db.execute(
            select(GroupAssignment.function_value).where(GroupAssignment.grouping_id == grouping.grouping_id)
        ).scalars()
    )
    return source_count, filtered_count, assignments


def test_label_filter_map_rename_group_pipeline(
    test_db: Session, testing_session_local: sessionmaker[Session], filter_scenario: DatabaseScenario
) -> None:
    test_db.add(
        Label(
            label_data_id=filter_scenario.label_datas["labels"].label_data_id,
            label_entity_group="MISC",
            label_word="world",
            label_start=27,
            label_end=32,
            label_score=0.2,
            label_dirty=False,
        )
    )

    source_count, filtered_count, assignments = _run_pipeline(
        test_db,
        testing_session_local,
        filter_scenario.label_groups["labels"].label_group_id,
        0.6,
    )

    assert source_count == len(filter_scenario.labels) + 1
    assert filtered_count == 3
    assert sorted(assignments) == ["test", "world", "world"]
    assert set(assignments) == {"test", "world"}


def test_catalog_xianxia_data_flows_through_runner_pipeline(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
    xianxia_labels_scenario: DatabaseScenario,
) -> None:
    label_group = xianxia_labels_scenario.label_groups["labels"]

    source_count, filtered_count, assignments = _run_pipeline(
        test_db,
        testing_session_local,
        label_group.label_group_id,
        0.985,
    )

    assert source_count == len(xianxia_labels_scenario.labels) == 2
    assert filtered_count == 1
    assert assignments == ["青石城"]
