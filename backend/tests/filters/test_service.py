import uuid
from dataclasses import dataclass

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.auth.models import User
from src.filters.data_types import (
    BoolData,
    BoolField,
    DataObj,
    FloatData,
    FloatField,
    IntData,
    IntField,
    Schema,
    StringData,
    StringField,
    data_adapter,
)
from src.filters.exceptions import (
    GroupingNotFoundException,
    GroupingNotReadyException,
    GroupingValueTypeMismatchException,
    InstanceNotFoundException,
    InvalidInstanceQueryException,
    InvalidSortKeyException,
    WorkflowNotFoundException,
    WorkflowNotReadyException,
)
from src.filters.functions import (
    Get,
)
from src.filters.models import (
    FunctionDefinition,
    GroupAssignment,
    Grouping,
    GroupingStatus,
    Instance,
    Workflow,
    WorkflowLabelGroup,
    WorkflowNovel,
    WorkflowStatus,
)
from src.filters.schemas import Frame, GroupFilter, InstanceQuery, SortDirection, SortKey
from src.filters.service import (
    query_functions,
    query_grouping,
    query_grouping_values,
    query_groupings,
    query_instances_of_workflow,
    query_instances_of_workflow_advanced,
    query_workflow,
    query_workflows,
)
from src.schemas import Model
from test_support.test_data.scenarios import DatabaseScenario


def _dump(value: Model) -> dict[str, object]:
    return value.model_dump(mode="json", by_alias=True, exclude_computed_fields=True)


@dataclass(frozen=True)
class AdvancedQueryData:
    workflow: Workflow
    instances: tuple[Instance, ...]
    groupings: dict[str, Grouping]


def _create_advanced_query_data(db: Session) -> AdvancedQueryData:
    schema = Schema(
        fields={
            "name": StringField(),
            "score": IntField(),
            "category": StringField(),
            "rank": IntField(),
            "active": BoolField(),
        }
    )
    workflow = Workflow(
        workflow_name="Advanced query test",
        schema=_dump(schema),
        workflow_status="complete",
    )
    db.add(workflow)
    db.flush()

    raw_instances = (
        ("beta", 1, "A", 1, True),
        ("beta", 1, "A", 2, False),
        ("alpha", 1, "B", 1, True),
        ("gamma", 2, "B", 2, True),
        ("alpha", 2, "A", 1, False),
        ("delta", 3, "B", 2, False),
    )
    instances = tuple(
        Instance(
            instance_id=uuid.UUID(int=index),
            workflow_id=workflow.workflow_id,
            value=_dump(
                DataObj(
                    fields={
                        "name": StringData(value=name),
                        "score": IntData(value=score),
                        "category": StringData(value=category),
                        "rank": IntData(value=rank),
                        "active": BoolData(value=active),
                    }
                )
            ),
        )
        for index, (name, score, category, rank, active) in enumerate(raw_instances, start=1)
    )
    db.add_all(instances)

    grouping_specs = {
        "category": Get(field_name="category", type="string"),
        "rank": Get(field_name="rank", type="int"),
        "active": Get(field_name="active", type="bool"),
    }
    groupings: dict[str, Grouping] = {}
    for name, function in grouping_specs.items():
        function_definition = FunctionDefinition(
            namespace="test",
            function_name=f"group-{name}",
            function_definition=_dump(function),
        )
        db.add(function_definition)
        db.flush()
        grouping = Grouping(
            workflow_id=workflow.workflow_id,
            function_definition_id=function_definition.function_definition_id,
            grouping_status=GroupingStatus.COMPLETE,
        )
        db.add(grouping)
        db.flush()
        groupings[name] = grouping

    for instance, (_, _, category, rank, active) in zip(instances, raw_instances, strict=True):
        db.add_all(
            [
                GroupAssignment(
                    grouping_id=groupings["category"].grouping_id,
                    instance_id=instance.instance_id,
                    function_value=category,
                ),
                GroupAssignment(
                    grouping_id=groupings["rank"].grouping_id,
                    instance_id=instance.instance_id,
                    function_value=rank,
                ),
                GroupAssignment(
                    grouping_id=groupings["active"].grouping_id,
                    instance_id=instance.instance_id,
                    function_value=active,
                ),
            ]
        )
    db.commit()
    return AdvancedQueryData(workflow=workflow, instances=instances, groupings=groupings)


def _create_scalar_sort_data(db: Session) -> AdvancedQueryData:
    schema = Schema(
        fields={
            "word": StringField(),
            "score": FloatField(),
            "start": IntField(),
            "end": IntField(),
            "low_score": BoolField(),
        }
    )
    workflow = Workflow(
        workflow_name="Scalar sort pagination",
        schema=_dump(schema),
        workflow_status=WorkflowStatus.COMPLETE,
    )
    db.add(workflow)
    db.flush()

    groupings: dict[str, Grouping] = {}
    for field_name, type_name in (("word", "string"), ("start", "int"), ("low_score", "bool")):
        definition = FunctionDefinition(
            namespace="scalar-sort",
            function_name=f"group-{field_name}",
            function_definition=_dump(Get(field_name=field_name, type=type_name)),
        )
        db.add(definition)
        db.flush()
        grouping = Grouping(
            workflow_id=workflow.workflow_id,
            function_definition_id=definition.function_definition_id,
            grouping_status=GroupingStatus.COMPLETE,
        )
        db.add(grouping)
        db.flush()
        groupings[field_name] = grouping

    rows = (
        ("青石城", 0.25, 10, 13, True),
        ("青石城", 0.25, 10, 13, True),
        ("林昀", 0.25, 4, 6, True),
        ("alpha", 0.50, 20, 25, True),
        ("beta", 0.50, 20, 24, True),
        ("白玫", 0.75, 2, 4, False),
        ("白玫", 0.75, 2, 4, False),
        ("gamma", 0.85, 15, 20, False),
        ("青石城", 0.85, 8, 11, False),
        ("delta", 0.95, 1, 6, False),
        ("林昀", 0.95, 1, 3, False),
        ("omega", 0.99, 30, 35, False),
    )
    instances: list[Instance] = []
    for word_val, score_val, start_val, end_val, low_val in rows:
        instance = Instance(
            workflow_id=workflow.workflow_id,
            value=_dump(
                DataObj(
                    fields={
                        "word": StringData(value=word_val),
                        "score": FloatData(value=score_val),
                        "start": IntData(value=start_val),
                        "end": IntData(value=end_val),
                        "low_score": BoolData(value=low_val),
                    }
                )
            ),
        )
        db.add(instance)
        db.flush()
        instances.append(instance)
        db.add_all(
            [
                GroupAssignment(
                    grouping_id=groupings["word"].grouping_id,
                    instance_id=instance.instance_id,
                    function_value=word_val,
                ),
                GroupAssignment(
                    grouping_id=groupings["start"].grouping_id,
                    instance_id=instance.instance_id,
                    function_value=start_val,
                ),
                GroupAssignment(
                    grouping_id=groupings["low_score"].grouping_id,
                    instance_id=instance.instance_id,
                    function_value=low_val,
                ),
            ]
        )
    db.commit()
    return AdvancedQueryData(workflow, tuple(instances), groupings)


def _query(
    db: Session,
    user: User,
    data: AdvancedQueryData,
    *,
    group_filters: list[GroupFilter] | None = None,
    sort_keys: list[SortKey] | None = None,
    limit: int = 50,
    cursor: uuid.UUID | None = None,
):
    return query_instances_of_workflow_advanced(
        db,
        user,
        InstanceQuery(
            frame=Frame(
                workflow_id=data.workflow.workflow_id,
                group_filters=group_filters or [],
                sort_keys=sort_keys or [],
            ),
            limit=limit,
            cursor=cursor,
        ),
    )


def _data_by_instance(data: AdvancedQueryData) -> dict[uuid.UUID, DataObj]:
    result: dict[uuid.UUID, DataObj] = {}
    for instance in data.instances:
        parsed = data_adapter.validate_python(instance.value)
        assert isinstance(parsed, DataObj)
        result[instance.instance_id] = parsed
    return result


def _collect_advanced_query_pages(
    db: Session,
    user: User,
    data: AdvancedQueryData,
    group_filters: list[GroupFilter],
    sort_keys: list[SortKey],
    *,
    page_size: int,
):
    results = []
    cursor = None
    while True:
        page = _query(
            db,
            user,
            data,
            group_filters=group_filters,
            sort_keys=sort_keys,
            limit=page_size,
            cursor=cursor,
        )
        if not page:
            break
        results.extend(page)
        cursor = page[-1].instance.instance_id
    return results


def test_frame_limits_groupings_to_ten() -> None:
    grouping_ids = [uuid.UUID(int=index) for index in range(1, 12)]

    Frame(
        workflow_id=uuid.UUID(int=100),
        group_filters=[GroupFilter(grouping_id=grouping_id, values=[]) for grouping_id in grouping_ids[:10]],
    )
    with pytest.raises(ValidationError, match="at most 10 items"):
        Frame(
            workflow_id=uuid.UUID(int=100),
            group_filters=[GroupFilter(grouping_id=grouping_id, values=[]) for grouping_id in grouping_ids],
        )


def test_group_filter_limits_selected_values_to_one_hundred() -> None:
    GroupFilter(
        grouping_id=uuid.UUID(int=1),
        values=[IntData(value=value) for value in range(100)],
    )
    with pytest.raises(ValidationError, match="at most 100 items"):
        GroupFilter(
            grouping_id=uuid.UUID(int=1),
            values=[IntData(value=value) for value in range(101)],
        )


def test_function_query_selects_metadata_without_loading_definition(
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    data = _create_advanced_query_data(test_db)

    results = query_functions(test_db, sample_scenario.users["admin"], "group", "test", 10, None)

    assert {result.function_name for result in results} == {f"group-{name}" for name in data.groupings}


def test_workflow_queries_include_scope_and_instance_count(
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    data = _create_advanced_query_data(test_db)
    novel = sample_scenario.novels["novel_1"]
    label_group = sample_scenario.label_groups["official"]
    test_db.add_all(
        [
            WorkflowNovel(workflow_id=data.workflow.workflow_id, novel_id=novel.novel_id),
            WorkflowLabelGroup(
                workflow_id=data.workflow.workflow_id,
                label_group_id=label_group.label_group_id,
            ),
        ]
    )
    test_db.commit()
    admin = sample_scenario.users["admin"]

    detail = query_workflow(test_db, admin, data.workflow.workflow_id)
    listed = query_workflows(test_db, admin, novel.novel_id, None, None, None, "Advanced", 10, None)

    assert detail.workflow_schema == Schema.model_validate(data.workflow.schema)
    assert detail.novel_ids == [novel.novel_id]
    assert detail.label_group_ids == [label_group.label_group_id]
    assert detail.instance_count == len(data.instances)
    assert [workflow.workflow_id for workflow in listed] == [data.workflow.workflow_id]


def test_grouping_queries_return_metadata_and_aggregated_values(
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    data = _create_advanced_query_data(test_db)
    admin = sample_scenario.users["admin"]

    groupings = query_groupings(test_db, admin, data.workflow.workflow_id, GroupingStatus.COMPLETE, 2, None)
    next_groupings = query_groupings(
        test_db,
        admin,
        data.workflow.workflow_id,
        GroupingStatus.COMPLETE,
        2,
        groupings[-1].grouping_id,
    )
    category = query_grouping(test_db, admin, data.groupings["category"].grouping_id)
    values = query_grouping_values(test_db, admin, category.grouping_id, None, 1, 0)
    next_values = query_grouping_values(test_db, admin, category.grouping_id, None, 1, 1)
    searched = query_grouping_values(test_db, admin, category.grouping_id, "A", 10, 0)

    assert len([*groupings, *next_groupings]) == 3
    assert category.output_type == "string"
    assert category.assignment_count == len(data.instances)
    assert {entry.value for entry in [*values, *next_values]} == {StringData(value="A"), StringData(value="B")}
    assert all(entry.count == 3 for entry in [*values, *next_values])
    assert [(entry.value, entry.count) for entry in searched] == [(StringData(value="A"), 3)]


def test_grouping_values_allow_active_groupings_and_reject_unreadable_groupings(
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    data = _create_advanced_query_data(test_db)
    admin = sample_scenario.users["admin"]

    with pytest.raises(InvalidInstanceQueryException, match="only for string"):
        query_grouping_values(test_db, admin, data.groupings["rank"].grouping_id, "1", 10, 0)

    for active_status in (GroupingStatus.PENDING, GroupingStatus.PROCESSING):
        data.groupings["category"].grouping_status = active_status
        test_db.commit()
        assert query_grouping_values(test_db, admin, data.groupings["category"].grouping_id, None, 10, 0)

    for unreadable_status in (GroupingStatus.NEW, GroupingStatus.FAILED):
        data.groupings["category"].grouping_status = unreadable_status
        test_db.commit()
        with pytest.raises(GroupingNotReadyException, match=unreadable_status.value):
            query_grouping_values(test_db, admin, data.groupings["category"].grouping_id, None, 10, 0)


def test_empty_simple_instance_query_distinguishes_accessible_and_inaccessible_workflows(
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    workflow = Workflow(
        workflow_name="Empty",
        schema=_dump(Schema()),
        workflow_status=WorkflowStatus.COMPLETE,
    )
    test_db.add(workflow)
    test_db.commit()

    assert query_instances_of_workflow(test_db, sample_scenario.users["admin"], workflow.workflow_id, 50, None) == []
    with pytest.raises(WorkflowNotFoundException):
        query_instances_of_workflow(test_db, sample_scenario.users["user"], workflow.workflow_id, 50, None)


def test_instance_queries_allow_active_workflows_and_reject_unreadable_workflows(
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    data = _create_advanced_query_data(test_db)
    admin = sample_scenario.users["admin"]
    for active_status in (WorkflowStatus.PENDING, WorkflowStatus.PROCESSING):
        data.workflow.workflow_status = active_status
        test_db.commit()
        simple_results = query_instances_of_workflow(test_db, admin, data.workflow.workflow_id, 50, None)
        advanced_results = _query(test_db, admin, data)
        assert len(simple_results) == len(data.instances)
        assert len(advanced_results) == len(data.instances)

    for unreadable_status in (WorkflowStatus.NEW, WorkflowStatus.FAILED):
        data.workflow.workflow_status = unreadable_status
        test_db.commit()
        with pytest.raises(WorkflowNotReadyException, match=unreadable_status.value):
            query_instances_of_workflow(test_db, admin, data.workflow.workflow_id, 50, None)
        with pytest.raises(WorkflowNotReadyException, match=unreadable_status.value):
            _query(test_db, admin, data)


def test_advanced_query_combines_groupings_with_and_and_values_with_or(
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    data = _create_advanced_query_data(test_db)

    results = _query(
        test_db,
        sample_scenario.users["admin"],
        data,
        group_filters=[
            GroupFilter(
                grouping_id=data.groupings["category"].grouping_id,
                values=[StringData(value="A"), StringData(value="B")],
            ),
            GroupFilter(
                grouping_id=data.groupings["rank"].grouping_id,
                values=[IntData(value=1)],
            ),
            GroupFilter(
                grouping_id=data.groupings["active"].grouping_id,
                values=[BoolData(value=True)],
            ),
        ],
    )

    assert [result.instance.instance_id for result in results] == [
        data.instances[0].instance_id,
        data.instances[2].instance_id,
    ]
    assert results[0].group_values == {
        data.groupings["category"].grouping_id: StringData(value="A"),
        data.groupings["rank"].grouping_id: IntData(value=1),
        data.groupings["active"].grouping_id: BoolData(value=True),
    }


def test_empty_group_values_project_without_filtering(
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    data = _create_advanced_query_data(test_db)

    results = _query(
        test_db,
        sample_scenario.users["admin"],
        data,
        group_filters=[GroupFilter(grouping_id=data.groupings["category"].grouping_id, values=[])],
    )

    assert [result.instance.instance_id for result in results] == [instance.instance_id for instance in data.instances]
    assert [result.group_values[data.groupings["category"].grouping_id] for result in results] == [
        StringData(value=value) for value in ("A", "A", "B", "B", "A", "B")
    ]


def test_advanced_query_paginates_lexicographically_with_mixed_directions(
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    data = _create_advanced_query_data(test_db)
    sort_keys = [
        SortKey(field_name="score", direction=SortDirection.ASCENDING),
        SortKey(field_name="name", direction=SortDirection.DESCENDING),
    ]

    first = _query(test_db, sample_scenario.users["admin"], data, sort_keys=sort_keys, limit=2)
    second = _query(
        test_db,
        sample_scenario.users["admin"],
        data,
        sort_keys=sort_keys,
        limit=2,
        cursor=first[-1].instance.instance_id,
    )
    third = _query(
        test_db,
        sample_scenario.users["admin"],
        data,
        sort_keys=sort_keys,
        limit=2,
        cursor=second[-1].instance.instance_id,
    )

    assert [result.instance.instance_id for result in [*first, *second, *third]] == [
        data.instances[index].instance_id for index in (0, 1, 2, 3, 4, 5)
    ]


def test_instances_paginate_across_all_scalar_sort_types(
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    admin = sample_scenario.users["admin"]
    data = _create_scalar_sort_data(test_db)
    parsed = _data_by_instance(data)
    group_filters = [
        GroupFilter(grouping_id=data.groupings[field_name].grouping_id, values=[])
        for field_name in ("word", "start", "low_score")
    ]

    def numeric_key(instance: Instance) -> tuple[float, int, str, int]:
        value = parsed[instance.instance_id]
        score = value.fields["score"]
        start = value.fields["start"]
        word = value.fields["word"]
        assert isinstance(score, FloatData)
        assert isinstance(start, IntData)
        assert isinstance(word, StringData)
        return score.value, -start.value, word.value, instance.instance_id.int

    numeric_sort = [
        SortKey(field_name="score", direction=SortDirection.ASCENDING),
        SortKey(field_name="start", direction=SortDirection.DESCENDING),
        SortKey(field_name="word", direction=SortDirection.ASCENDING),
    ]
    numeric_results = _collect_advanced_query_pages(
        test_db,
        admin,
        data,
        group_filters,
        numeric_sort,
        page_size=4,
    )
    assert [result.instance.instance_id for result in numeric_results] == [
        instance.instance_id for instance in sorted(data.instances, key=numeric_key)
    ]

    def boolean_key(instance: Instance) -> tuple[bool, int, str, int]:
        value = parsed[instance.instance_id]
        low_score = value.fields["low_score"]
        end = value.fields["end"]
        word = value.fields["word"]
        assert isinstance(low_score, BoolData)
        assert isinstance(end, IntData)
        assert isinstance(word, StringData)
        return low_score.value, -end.value, word.value, instance.instance_id.int

    boolean_sort = [
        SortKey(field_name="low_score", direction=SortDirection.ASCENDING),
        SortKey(field_name="end", direction=SortDirection.DESCENDING),
        SortKey(field_name="word", direction=SortDirection.ASCENDING),
    ]
    boolean_results = _collect_advanced_query_pages(
        test_db,
        admin,
        data,
        group_filters,
        boolean_sort,
        page_size=5,
    )
    assert [result.instance.instance_id for result in boolean_results] == [
        instance.instance_id for instance in sorted(data.instances, key=boolean_key)
    ]

    assert len({result.instance.instance_id for result in numeric_results}) == len(data.instances)
    assert {parsed_instance.fields["low_score"].value for parsed_instance in parsed.values()} == {False, True}
    words: list[str] = []
    for parsed_instance in parsed.values():
        word = parsed_instance.fields["word"]
        assert isinstance(word, StringData)
        words.append(word.value)
    assert len(set(words)) < len(words)
    assert any(not word.isascii() for word in words)
    for result in numeric_results:
        instance_data = parsed[result.instance.instance_id]
        assert result.group_values[data.groupings["word"].grouping_id] == instance_data.fields["word"]
        assert result.group_values[data.groupings["start"].grouping_id] == instance_data.fields["start"]
        assert result.group_values[data.groupings["low_score"].grouping_id] == instance_data.fields["low_score"]


def test_advanced_query_validation_access_and_error_cases(
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    data = _create_advanced_query_data(test_db)
    admin = sample_scenario.users["admin"]

    with pytest.raises(GroupingValueTypeMismatchException, match="different type"):
        _query(
            test_db,
            admin,
            data,
            group_filters=[
                GroupFilter(grouping_id=data.groupings["category"].grouping_id, values=[IntData(value=1)])
            ],
        )

    with pytest.raises(GroupingNotFoundException, match="Grouping IDs not found"):
        _query(test_db, admin, data, group_filters=[GroupFilter(grouping_id=uuid.UUID(int=1000), values=[])])

    with pytest.raises(InvalidSortKeyException, match="not a valid field"):
        _query(test_db, admin, data, sort_keys=[SortKey(field_name="missing", direction=SortDirection.ASCENDING)])

    with pytest.raises(WorkflowNotFoundException):
        _query(test_db, sample_scenario.users["user"], data)

    other_workflow = Workflow(workflow_name="Other", schema=data.workflow.schema)
    test_db.add(other_workflow)
    test_db.flush()
    other_instance = Instance(workflow_id=other_workflow.workflow_id, value=data.instances[0].value)
    test_db.add(other_instance)
    test_db.commit()
    with pytest.raises(InstanceNotFoundException):
        _query(test_db, admin, data, cursor=other_instance.instance_id)

    data.groupings["category"].grouping_status = GroupingStatus.PROCESSING
    test_db.commit()
    assert _query(
        test_db,
        admin,
        data,
        group_filters=[GroupFilter(grouping_id=data.groupings["category"].grouping_id, values=[])],
    )

    data.groupings["category"].grouping_status = GroupingStatus.FAILED
    test_db.commit()
    with pytest.raises(GroupingNotReadyException, match="failed"):
        _query(
            test_db,
            admin,
            data,
            group_filters=[GroupFilter(grouping_id=data.groupings["category"].grouping_id, values=[])],
        )
