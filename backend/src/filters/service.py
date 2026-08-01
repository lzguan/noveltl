from uuid import UUID

from sqlalchemy import Boolean, Float, Integer, and_, cast, exists, or_, select, type_coerce
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session, aliased

from src.auth.models import User
from src.filters.data_types import BoolField, IntField, Schema, StringField, data_adapter
from src.filters.exceptions import (
    FunctionNotFoundException,
    GroupingNotFoundException,
    GroupingNotReadyException,
    GroupingValueTypeMismatchException,
    InstanceNotFoundException,
    UnsupportedSortTypeException,
    WorkflowNotFoundException,
    WorkflowNotReadyException,
)
from src.filters.functions import function_adapter
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
    WorkflowUseCase,
)
from src.filters.permissions import instance_mod_access_select, workflow_mod_access_select
from src.filters.schemas import (
    FunctionDefinitionMeta,
    InstanceQuery,
    InstanceQueryResult,
    SortDirection,
    validate_frame_workflow,
)


def query_function_namespaces(db: Session, current_user: User, search: str | None) -> list[str]:
    query = select(FunctionDefinition.namespace).distinct()
    if search:
        query = query.where(FunctionDefinition.namespace.ilike(f"%{search}%"))
    result = db.execute(query).scalars().all()
    return list(result)


def query_functions(
    db: Session, current_user: User, search: str | None, namespace: str | None, limit: int, cursor: UUID | None
) -> list[FunctionDefinitionMeta]:
    query = select(
        FunctionDefinition.function_definition_id, FunctionDefinition.namespace, FunctionDefinition.function_name
    )
    if search:
        query = query.where(
            or_(
                FunctionDefinition.function_name.ilike(f"%{search}%"), FunctionDefinition.namespace.ilike(f"%{search}%")
            )
        )
    if namespace:
        query = query.where(FunctionDefinition.namespace == namespace)
    if cursor:
        query = query.where(FunctionDefinition.function_definition_id > cursor)
    query = query.limit(limit).order_by(FunctionDefinition.function_definition_id)
    functions = db.execute(query)
    return [
        FunctionDefinitionMeta(
            function_definition_id=row.function_definition_id, namespace=row.namespace, function_name=row.function_name
        )
        for row in functions
    ]


def query_function(db: Session, current_user: User, function_definition_id: UUID) -> FunctionDefinition:
    try:
        return db.execute(
            select(FunctionDefinition).where(FunctionDefinition.function_definition_id == function_definition_id)
        ).scalar_one()
    except NoResultFound as e:
        raise FunctionNotFoundException(f"Function with ID {function_definition_id} not found.") from e


def query_workflows(
    db: Session,
    current_user: User,
    novel_id: UUID | None,
    label_group_id: UUID | None,
    use_case: WorkflowUseCase | None,
    status: WorkflowStatus | None,
    search: str | None,
    limit: int,
    cursor: UUID | None,
) -> list[Workflow]:
    q = select(Workflow)
    if novel_id is not None:
        q = q.where(
            exists(
                select(1)
                .select_from(WorkflowNovel)
                .where(and_(WorkflowNovel.novel_id == novel_id, Workflow.workflow_id == WorkflowNovel.workflow_id))
            )
        )
    if label_group_id is not None:
        q = q.where(
            exists(
                select(1)
                .select_from(WorkflowLabelGroup)
                .where(
                    and_(
                        WorkflowLabelGroup.label_group_id == label_group_id,
                        Workflow.workflow_id == WorkflowLabelGroup.workflow_id,
                    )
                )
            )
        )
    if use_case is not None:
        q = q.where(Workflow.use_case == use_case)
    if status is not None:
        q = q.where(Workflow.workflow_status == status)
    if search is not None:
        q = q.where(Workflow.workflow_name.ilike(f"%{search}%"))
    if cursor is not None:
        q = q.where(Workflow.workflow_id > cursor)
    q = q.order_by(Workflow.workflow_id).limit(limit)
    q = workflow_mod_access_select(q, current_user)
    return list(db.execute(q).scalars().all())


def query_workflow(db: Session, current_user: User, workflow_id: UUID) -> Workflow:
    q = select(Workflow).where(Workflow.workflow_id == workflow_id)
    q = workflow_mod_access_select(q, current_user)
    try:
        return db.execute(q).scalar_one()
    except NoResultFound as e:
        raise WorkflowNotFoundException(f"Workflow with ID {workflow_id} not found or not accessible.") from e


def query_instances_of_workflow(
    db: Session, current_user: User, workflow_id: UUID, limit: int, cursor: UUID | None
) -> list[Instance]:
    complete_workflow = exists(
        select(1)
        .select_from(Workflow)
        .where(Workflow.workflow_id == Instance.workflow_id)
        .where(Workflow.workflow_status == WorkflowStatus.COMPLETE)
    )
    q = select(Instance).where(Instance.workflow_id == workflow_id).where(complete_workflow)
    q = instance_mod_access_select(q, current_user)
    if cursor is not None:
        q = q.where(Instance.instance_id > cursor)
    q = q.order_by(Instance.instance_id).limit(limit)
    instances = list(db.execute(q).scalars().all())
    if not instances:
        workflow = query_workflow(db, current_user, workflow_id)
        if workflow.workflow_status != WorkflowStatus.COMPLETE:
            raise WorkflowNotReadyException(
                f"Workflow {workflow_id} is {workflow.workflow_status.value} and cannot be queried for instances."
            )
    return instances


def query_instances_of_workflow_advanced(
    db: Session, current_user: User, request: InstanceQuery
) -> list[InstanceQueryResult]:
    # Validate the workflow and schema
    workflow_id = request.frame.workflow_id
    try:
        workflow = db.execute(
            workflow_mod_access_select(select(Workflow).where(Workflow.workflow_id == workflow_id), current_user)
        ).scalar_one()
    except NoResultFound as e:
        raise WorkflowNotFoundException(f"Workflow with ID {workflow_id} not found or not accessible.") from e
    if workflow.workflow_status != WorkflowStatus.COMPLETE:
        raise WorkflowNotReadyException(
            f"Workflow {workflow_id} is {workflow.workflow_status.value} and cannot be queried for instances."
        )

    instance_query = select(Instance).where(Instance.workflow_id == workflow_id)

    # Grouping filters
    group_select = (
        select(Grouping, FunctionDefinition)
        .where(Grouping.workflow_id == workflow_id)
        .where(Grouping.grouping_id.in_([gf.grouping_id for gf in request.frame.group_filters]))
        .join(FunctionDefinition, Grouping.function_definition_id == FunctionDefinition.function_definition_id)
    )
    group_rows = db.execute(group_select).all()
    groups = {
        grouping.grouping_id: (grouping, function_definition)
        for grouping, function_definition in group_rows
    }
    if len(groups) != len(request.frame.group_filters):
        missing_ids = {group_filter.grouping_id for group_filter in request.frame.group_filters} - groups.keys()
        raise GroupingNotFoundException(f"Grouping IDs not found in workflow {workflow_id}: {missing_ids}")

    assignment_aliases = [
        aliased(GroupAssignment, name=f"selected_group_assignment_{index}")
        for index in range(len(request.frame.group_filters))
    ]
    group_value_types: list[str] = []
    for index, group_filter in enumerate(request.frame.group_filters):
        grouping, function_definition = groups[group_filter.grouping_id]
        if grouping.grouping_status != GroupingStatus.COMPLETE:
            raise GroupingNotReadyException(
                f"Grouping {grouping.grouping_id} is {grouping.grouping_status.value} and cannot be queried."
            )
        function = function_adapter.validate_python(function_definition.function_definition)
        output_type = function.signature.output
        if not isinstance(output_type, (StringField, IntField, BoolField)):
            raise ValueError(
                f"Grouping function {function_definition.function_definition_id} must return string, int, or bool."
            )
        if any(value.type != output_type.type for value in group_filter.values):
            raise GroupingValueTypeMismatchException(
                f"Grouping function {function_definition.function_definition_id} returns {output_type.type}, "
                "but one or more selected values have a different type."
            )

        assignment_alias = assignment_aliases[index]
        instance_query = instance_query.join(
            assignment_alias,
            and_(
                assignment_alias.instance_id == Instance.instance_id,
                assignment_alias.grouping_id == grouping.grouping_id,
            ),
        ).add_columns(assignment_alias.function_value.label(f"group_value_{index}"))
        if group_filter.values:
            instance_query = instance_query.where(
                assignment_alias.function_value.in_(
                    [type_coerce(value.value, postgresql.JSONB) for value in group_filter.values]
                )
            )
        group_value_types.append(output_type.type)

    # Sorting + cursor handling
    schema = Schema.model_validate(workflow.schema)
    validate_frame_workflow(request.frame, schema)

    sort_columns = []
    for sort_key in request.frame.sort_keys:
        key = sort_key.field_name
        if schema.fields[key].type == "string":
            sort_column = Instance.value["fields"][key]["value"].astext
        elif schema.fields[key].type == "int":
            sort_column = cast(Instance.value["fields"][key]["value"], Integer)
        elif schema.fields[key].type == "float":
            sort_column = cast(Instance.value["fields"][key]["value"], Float)
        elif schema.fields[key].type == "bool":
            sort_column = cast(cast(Instance.value["fields"][key]["value"], Boolean), Integer)
        else:
            raise UnsupportedSortTypeException(f"Unsupported sort key type: {schema.fields[key].type}")
        sort_columns.append((sort_key, sort_column))

    if request.cursor is not None:
        try:
            current = db.execute(
                select(Instance).where(Instance.instance_id == request.cursor, Instance.workflow_id == workflow_id)
            ).scalar_one()
        except NoResultFound as e:
            raise InstanceNotFoundException(
                f"Cursor with ID {request.cursor} not found in workflow {workflow_id}."
            ) from e
        data = data_adapter.validate_python(current.value)
        if data.obj is False:
            raise ValueError(f"Cursor with ID {request.cursor} does not contain an object value.")
        cursor_conditions = []
        equal_prefix = []
        for sort_key, sort_column in sort_columns:
            cursor_value = data.fields[sort_key.field_name].value
            if schema.fields[sort_key.field_name].type == "bool":
                if not isinstance(cursor_value, bool):
                    raise ValueError(f"Cursor field {sort_key.field_name} does not contain a boolean value.")
                cursor_value = int(cursor_value)
            if sort_key.direction == SortDirection.ASCENDING:
                after_cursor = sort_column > cursor_value
            else:
                after_cursor = sort_column < cursor_value
            if equal_prefix:
                cursor_conditions.append(and_(*equal_prefix, after_cursor))
            else:
                cursor_conditions.append(after_cursor)
            equal_prefix.append(sort_column == cursor_value)

        instance_id_condition = Instance.instance_id > request.cursor
        if equal_prefix:
            cursor_conditions.append(and_(*equal_prefix, instance_id_condition))
        else:
            cursor_conditions.append(instance_id_condition)
        instance_query = instance_query.where(or_(*cursor_conditions))

    for sort_key, sort_column in sort_columns:
        if sort_key.direction == SortDirection.ASCENDING:
            instance_query = instance_query.order_by(sort_column.asc())
        else:
            instance_query = instance_query.order_by(sort_column.desc())
    instance_query = instance_query.order_by(Instance.instance_id.asc())
    instance_query = instance_query.limit(request.limit)

    rows = db.execute(instance_query).all()
    return [
        InstanceQueryResult.model_validate(
            {
                "instance": row[0],
                "group_values": {
                    group_filter.grouping_id: {
                        "type": group_value_types[index],
                        "value": row[index + 1],
                    }
                    for index, group_filter in enumerate(request.frame.group_filters)
                },
            }
        )
        for row in rows
    ]
