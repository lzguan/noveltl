from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Float,
    Integer,
    String,
    and_,
    cast,
    exists,
    func,
    insert,
    or_,
    select,
    type_coerce,
    update,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import Session, aliased

from src.auth.models import User
from src.filters.data_types import BoolField, IntField, Schema, StringField, data_adapter, extends
from src.filters.dispatch.dispatcher import RunnerDispatcher
from src.filters.exceptions import (
    FunctionAlreadyExistsException,
    FunctionNotFoundException,
    GroupingAlreadyExistsException,
    GroupingNotFoundException,
    GroupingNotReadyException,
    GroupingValueTypeMismatchException,
    InstanceNotFoundException,
    InvalidInstanceQueryException,
    InvalidRunnerRequestException,
    RunnerEnqueueFailedException,
    UnsupportedSortTypeException,
    WorkflowNotFoundException,
    WorkflowNotReadyException,
)
from src.filters.functions import FunctionType, function_adapter
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
from src.filters.permissions import (
    grouping_mod_access_select,
    instance_mod_access_select,
    workflow_mod_access_select,
    workflow_mod_access_update,
)
from src.filters.runners.python.filter_runner import PythonFilterInput
from src.filters.runners.python.group_runner import PythonGroupInput
from src.filters.runners.python.label_source_runner import LABEL_SOURCE_SCHEMA, PythonLabelSourceInput
from src.filters.runners.python.map_runner import PythonMapInput
from src.filters.schemas import (
    CreateFunctionDefinitionRequest,
    FunctionDefinitionMeta,
    FunctionDefinitionResponse,
    GroupingResponse,
    GroupOperationAccepted,
    GroupValueCount,
    InstanceQuery,
    InstanceQueryResult,
    PythonFilterRequest,
    PythonGroupRequest,
    PythonLabelSourceRequest,
    PythonMapRequest,
    RenameWorkflowRequest,
    RunnerInput,
    SortDirection,
    WorkflowOperationAccepted,
    WorkflowResponse,
    validate_frame_workflow,
)
from src.labels.models import LabelGroup
from src.labels.permissions import label_group_mod_access_select


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


def query_workflow(db: Session, current_user: User, workflow_id: UUID) -> WorkflowResponse:
    q = select(Workflow).where(Workflow.workflow_id == workflow_id)
    q = workflow_mod_access_select(q, current_user)
    try:
        workflow = db.execute(q).scalar_one()
    except NoResultFound as e:
        raise WorkflowNotFoundException(f"Workflow with ID {workflow_id} not found or not accessible.") from e
    novel_ids = list(
        db.execute(
            select(WorkflowNovel.novel_id)
            .where(WorkflowNovel.workflow_id == workflow_id)
            .order_by(WorkflowNovel.novel_id)
        ).scalars()
    )
    label_group_ids = list(
        db.execute(
            select(WorkflowLabelGroup.label_group_id)
            .where(WorkflowLabelGroup.workflow_id == workflow_id)
            .order_by(WorkflowLabelGroup.label_group_id)
        ).scalars()
    )
    instance_count = db.scalar(select(func.count(Instance.instance_id)).where(Instance.workflow_id == workflow_id)) or 0
    return WorkflowResponse.model_validate(
        {
            "workflow_id": workflow.workflow_id,
            "workflow_name": workflow.workflow_name,
            "use_case": workflow.use_case,
            "schema": workflow.schema,
            "job_id": workflow.job_id,
            "workflow_status": workflow.workflow_status,
            "workflow_message": workflow.workflow_message,
            "novel_ids": novel_ids,
            "label_group_ids": label_group_ids,
            "instance_count": instance_count,
            "created_at": workflow.created_at,
            "updated_at": workflow.updated_at,
        }
    )


def query_groupings(
    db: Session,
    current_user: User,
    workflow_id: UUID,
    status: GroupingStatus | None,
    limit: int,
    cursor: UUID | None,
) -> list[Grouping]:
    workflow_query = workflow_mod_access_select(
        select(Workflow.workflow_id).where(Workflow.workflow_id == workflow_id),
        current_user,
    )
    if db.execute(workflow_query).scalar_one_or_none() is None:
        raise WorkflowNotFoundException(f"Workflow with ID {workflow_id} not found or not accessible.")
    query = select(Grouping).where(Grouping.workflow_id == workflow_id)
    if status is not None:
        query = query.where(Grouping.grouping_status == status)
    if cursor is not None:
        query = query.where(Grouping.grouping_id > cursor)
    query = grouping_mod_access_select(query, current_user)
    return list(db.execute(query.order_by(Grouping.grouping_id).limit(limit)).scalars())


def query_grouping(db: Session, current_user: User, grouping_id: UUID) -> GroupingResponse:
    assignment_count = (
        select(func.count(GroupAssignment.group_assignment_id))
        .where(GroupAssignment.grouping_id == Grouping.grouping_id)
        .correlate(Grouping)
        .scalar_subquery()
    )
    query = (
        select(Grouping, FunctionDefinition, assignment_count)
        .join(FunctionDefinition, FunctionDefinition.function_definition_id == Grouping.function_definition_id)
        .where(Grouping.grouping_id == grouping_id)
    )
    query = grouping_mod_access_select(query, current_user)
    try:
        grouping, function_definition, count = db.execute(query).one()
    except NoResultFound as e:
        raise GroupingNotFoundException(f"Grouping with ID {grouping_id} not found or not accessible.") from e
    function = function_adapter.validate_python(function_definition.function_definition)
    output = function.signature.output
    if not isinstance(output, (StringField, IntField, BoolField)) or output.mutable:
        raise ValueError(
            f"Grouping function {function_definition.function_definition_id} must return an immutable "
            "string, integer, or boolean."
        )
    return GroupingResponse(
        grouping_id=grouping.grouping_id,
        workflow_id=grouping.workflow_id,
        function_definition=FunctionDefinitionMeta(
            function_definition_id=function_definition.function_definition_id,
            namespace=function_definition.namespace,
            function_name=function_definition.function_name,
        ),
        output_type=output.type,
        job_id=grouping.job_id,
        grouping_status=grouping.grouping_status,
        grouping_message=grouping.grouping_message,
        assignment_count=count,
        created_at=grouping.created_at,
        updated_at=grouping.updated_at,
    )


def query_grouping_values(
    db: Session,
    current_user: User,
    grouping_id: UUID,
    search: str | None,
    limit: int,
    offset: int,
) -> list[GroupValueCount]:
    grouping = query_grouping(db, current_user, grouping_id)
    if grouping.grouping_status != GroupingStatus.COMPLETE:
        raise GroupingNotReadyException(
            f"Grouping {grouping_id} is {grouping.grouping_status.value} and cannot be queried for values."
        )
    if search is not None and grouping.output_type != "string":
        raise InvalidInstanceQueryException("Grouping value search is supported only for string-valued groupings.")

    value_count = func.count(GroupAssignment.group_assignment_id).label("value_count")
    query = (
        select(GroupAssignment.function_value, value_count)
        .where(GroupAssignment.grouping_id == grouping_id)
        .group_by(GroupAssignment.function_value)
    )
    if search is not None:
        query = query.where(cast(GroupAssignment.function_value, String).ilike(f"%{search}%"))
    rows = db.execute(
        query.order_by(value_count.desc(), GroupAssignment.function_value.asc()).offset(offset).limit(limit)
    ).all()
    return [
        GroupValueCount.model_validate(
            {
                "value": {"type": grouping.output_type, "value": value},
                "count": count,
            }
        )
        for value, count in rows
    ]


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
    groups = {grouping.grouping_id: (grouping, function_definition) for grouping, function_definition in group_rows}
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


def create_function_definition(
    db: Session,
    request: CreateFunctionDefinitionRequest,
) -> FunctionDefinitionResponse:
    """Validate and save a function in the shared immutable registry."""
    function = function_adapter.validate_python(request.function_definition)
    try:
        definition = db.execute(
            insert(FunctionDefinition)
            .values(
                namespace=request.namespace,
                function_name=request.function_name,
                function_definition=function.model_dump(
                    mode="json",
                    by_alias=True,
                    exclude_computed_fields=True,
                ),
            )
            .returning(FunctionDefinition)
        ).scalar_one()
        db.commit()
    except IntegrityError:
        db.rollback()
        existing_id = db.scalar(
            select(FunctionDefinition.function_definition_id).where(
                FunctionDefinition.namespace == request.namespace,
                FunctionDefinition.function_name == request.function_name,
            )
        )
        if existing_id is not None:
            raise FunctionAlreadyExistsException(
                f"Function '{request.namespace}.{request.function_name}' already exists."
            ) from None
        raise
    return FunctionDefinitionResponse.model_validate(definition)


def rename_workflow(
    db: Session,
    current_user: User,
    workflow_id: UUID,
    request: RenameWorkflowRequest,
) -> WorkflowResponse:
    """Rename an accessible workflow without changing its execution state."""
    statement = (
        update(Workflow)
        .where(Workflow.workflow_id == workflow_id)
        .values(workflow_name=request.workflow_name)
        .returning(Workflow.workflow_id)
    )
    statement = workflow_mod_access_update(statement, current_user)
    updated_id = db.scalar(statement)
    if updated_id is None:
        db.rollback()
        raise WorkflowNotFoundException(f"Workflow with ID {workflow_id} not found or not accessible.")
    db.commit()
    return query_workflow(db, current_user, workflow_id)


def _parse_fn_def(db: Session, function_definition_id: UUID) -> FunctionType:
    """Load and parse a saved function definition."""
    try:
        definition = db.execute(
            select(FunctionDefinition).where(FunctionDefinition.function_definition_id == function_definition_id)
        ).scalar_one()
    except NoResultFound as exc:
        raise FunctionNotFoundException(f"Function definition with ID {function_definition_id} not found.") from exc
    return function_adapter.validate_python(definition.function_definition)


def _parse_workflow_schema(
    db: Session,
    current_user: User,
    workflow_id: UUID,
) -> tuple[Workflow, Schema]:
    """Load an accessible completed workflow and parse its schema."""
    statement = workflow_mod_access_select(
        select(Workflow).where(Workflow.workflow_id == workflow_id),
        current_user,
    )
    try:
        workflow = db.execute(statement).scalar_one()
    except NoResultFound as exc:
        raise WorkflowNotFoundException(f"Workflow with ID {workflow_id} not found or not accessible.") from exc
    if workflow.workflow_status != WorkflowStatus.COMPLETE:
        raise WorkflowNotReadyException(
            f"Workflow {workflow_id} is {workflow.workflow_status.value} and must be complete."
        )
    return workflow, Schema.model_validate(workflow.schema)


def dispatch_workflow_runner(
    db: Session,
    dispatcher: RunnerDispatcher,
    workflow_id: UUID,
    job_id: UUID,
    runner_input: RunnerInput,
) -> None:
    """Publish a committed workflow job and persist a definite publication failure."""
    try:
        dispatcher.enqueue(job_id, runner_input)
    except RunnerEnqueueFailedException:
        db.execute(
            update(Workflow)
            .where(Workflow.workflow_id == workflow_id, Workflow.job_id == job_id)
            .values(
                workflow_status=WorkflowStatus.FAILED,
                workflow_message="Runner publication failed.",
            )
        )
        db.commit()
        raise


def dispatch_grouping_runner(
    db: Session,
    dispatcher: RunnerDispatcher,
    grouping_id: UUID,
    job_id: UUID,
    runner_input: RunnerInput,
) -> None:
    """Publish a committed grouping job and persist a definite publication failure."""
    try:
        dispatcher.enqueue(job_id, runner_input)
    except RunnerEnqueueFailedException:
        db.execute(
            update(Grouping)
            .where(Grouping.grouping_id == grouping_id, Grouping.job_id == job_id)
            .values(
                grouping_status=GroupingStatus.FAILED,
                grouping_message="Runner publication failed.",
            )
        )
        db.commit()
        raise


def run_label_source(
    db: Session,
    current_user: User,
    dispatcher: RunnerDispatcher,
    request: PythonLabelSourceRequest,
) -> WorkflowOperationAccepted:
    """Create and dispatch a label-source workflow operation."""
    # Label-source workflows require novel edit access but only read access to
    # the selected label group.
    statement = select(LabelGroup).where(LabelGroup.label_group_id == request.label_group_id)
    statement = label_group_mod_access_select(
        statement,
        current_user,
        novel_edit_only=True,
    )
    try:
        label_group = db.execute(statement).scalar_one()
    except NoResultFound as exc:
        raise WorkflowNotFoundException(
            f"Label group with ID {request.label_group_id} not found or not accessible."
        ) from exc

    job_id = uuid4()
    workflow = db.execute(
        insert(Workflow)
        .values(
            workflow_name=request.output_name,
            use_case=WorkflowUseCase.ADVANCED,
            schema=LABEL_SOURCE_SCHEMA.model_dump(
                mode="json",
                by_alias=True,
                exclude_computed_fields=True,
            ),
            job_id=job_id,
            workflow_status=WorkflowStatus.PENDING,
        )
        .returning(Workflow)
    ).scalar_one()
    db.add_all(
        [
            WorkflowNovel(workflow_id=workflow.workflow_id, novel_id=label_group.novel_id),
            WorkflowLabelGroup(workflow_id=workflow.workflow_id, label_group_id=label_group.label_group_id),
        ]
    )
    db.commit()

    runner_input = PythonLabelSourceInput(
        runtime_name="python",
        runner_name="ls",
        label_group_id=label_group.label_group_id,
        output_workflow_id=workflow.workflow_id,
    )
    dispatch_workflow_runner(db, dispatcher, workflow.workflow_id, job_id, runner_input)
    return WorkflowOperationAccepted(
        job_id=job_id,
        workflow=query_workflow(db, current_user, workflow.workflow_id),
    )


def validate_object_function(function: FunctionType, operation_name: str) -> Schema:
    """Return the single object input schema required by a workflow operation."""
    if len(function.signature.args) != 1 or not isinstance(function.signature.args[0], Schema):
        raise InvalidRunnerRequestException(f"A {operation_name} function must accept exactly one object schema.")
    return function.signature.args[0]


def create_derived_workflow(
    db: Session,
    source_workflow_id: UUID,
    workflow_name: str | None,
    schema: Schema,
    job_id: UUID,
) -> Workflow:
    """Create and commit a pending workflow with its inherited permission scope."""
    workflow = db.execute(
        insert(Workflow)
        .values(
            workflow_name=workflow_name,
            use_case=WorkflowUseCase.ADVANCED,
            schema=schema.model_dump(mode="json", by_alias=True, exclude_computed_fields=True),
            job_id=job_id,
            workflow_status=WorkflowStatus.PENDING,
        )
        .returning(Workflow)
    ).scalar_one()

    # Derived workflows inherit every novel and label-group association used to
    # authorize access to their source workflow.
    novel_ids = db.scalars(select(WorkflowNovel.novel_id).where(WorkflowNovel.workflow_id == source_workflow_id)).all()
    label_group_ids = db.scalars(
        select(WorkflowLabelGroup.label_group_id).where(WorkflowLabelGroup.workflow_id == source_workflow_id)
    ).all()
    db.add_all(WorkflowNovel(workflow_id=workflow.workflow_id, novel_id=novel_id) for novel_id in novel_ids)
    db.add_all(
        WorkflowLabelGroup(workflow_id=workflow.workflow_id, label_group_id=label_group_id)
        for label_group_id in label_group_ids
    )
    db.commit()
    return workflow


def run_map(
    db: Session,
    current_user: User,
    dispatcher: RunnerDispatcher,
    request: PythonMapRequest,
) -> WorkflowOperationAccepted:
    """Create and dispatch a map workflow operation."""
    source, source_schema = _parse_workflow_schema(db, current_user, request.source_workflow_id)
    function = _parse_fn_def(db, request.function_definition_id)
    required_schema = validate_object_function(function, "map")
    if not extends(source_schema, required_schema):
        raise InvalidRunnerRequestException("Source workflow schema does not satisfy the map function input schema.")
    output_schema = function.signature.output
    if not isinstance(output_schema, Schema):
        raise InvalidRunnerRequestException("A map function must return an object schema.")

    job_id = uuid4()
    output = create_derived_workflow(
        db,
        source.workflow_id,
        request.output_name,
        output_schema,
        job_id,
    )
    runner_input = PythonMapInput(
        runtime_name="python",
        runner_name="map",
        source_workflow_id=source.workflow_id,
        output_workflow_id=output.workflow_id,
        function_definition_id=request.function_definition_id,
    )
    dispatch_workflow_runner(db, dispatcher, output.workflow_id, job_id, runner_input)
    return WorkflowOperationAccepted(
        job_id=job_id,
        workflow=query_workflow(db, current_user, output.workflow_id),
    )


def run_filter(
    db: Session,
    current_user: User,
    dispatcher: RunnerDispatcher,
    request: PythonFilterRequest,
) -> WorkflowOperationAccepted:
    """Create and dispatch a filter workflow operation."""
    source, source_schema = _parse_workflow_schema(db, current_user, request.source_workflow_id)
    function = _parse_fn_def(db, request.function_definition_id)
    required_schema = validate_object_function(function, "filter")
    if not extends(source_schema, required_schema):
        raise InvalidRunnerRequestException("Source workflow schema does not satisfy the filter function input schema.")
    if not isinstance(function.signature.output, BoolField):
        raise InvalidRunnerRequestException("A filter function must return a boolean.")

    job_id = uuid4()
    output = create_derived_workflow(
        db,
        source.workflow_id,
        request.output_name,
        source_schema,
        job_id,
    )
    runner_input = PythonFilterInput(
        runtime_name="python",
        runner_name="filter",
        source_workflow_id=source.workflow_id,
        output_workflow_id=output.workflow_id,
        function_definition_id=request.function_definition_id,
    )
    dispatch_workflow_runner(db, dispatcher, output.workflow_id, job_id, runner_input)
    return WorkflowOperationAccepted(
        job_id=job_id,
        workflow=query_workflow(db, current_user, output.workflow_id),
    )


def run_group(
    db: Session,
    current_user: User,
    dispatcher: RunnerDispatcher,
    request: PythonGroupRequest,
) -> GroupOperationAccepted:
    """Create and dispatch a grouping operation."""
    workflow, workflow_schema = _parse_workflow_schema(db, current_user, request.workflow_id)
    function = _parse_fn_def(db, request.function_definition_id)
    required_schema = validate_object_function(function, "grouping")
    if not extends(workflow_schema, required_schema):
        raise InvalidRunnerRequestException("Workflow schema does not satisfy the grouping function input schema.")
    mutable_dependencies = [
        field_name for field_name in required_schema.fields if workflow_schema.fields[field_name].mutable
    ]
    if mutable_dependencies:
        raise InvalidRunnerRequestException(
            "Grouping functions cannot depend on mutable workflow fields: " + ", ".join(mutable_dependencies)
        )
    output = function.signature.output
    if not isinstance(output, StringField | IntField | BoolField) or output.mutable:
        raise InvalidRunnerRequestException("A grouping function must return an immutable string, integer, or boolean.")

    job_id = uuid4()
    try:
        grouping = db.execute(
            insert(Grouping)
            .values(
                workflow_id=workflow.workflow_id,
                function_definition_id=request.function_definition_id,
                job_id=job_id,
                grouping_status=GroupingStatus.PENDING,
            )
            .returning(Grouping)
        ).scalar_one()
        db.commit()
    except IntegrityError:
        db.rollback()
        existing_id = db.scalar(
            select(Grouping.grouping_id).where(
                Grouping.workflow_id == workflow.workflow_id,
                Grouping.function_definition_id == request.function_definition_id,
            )
        )
        if existing_id is not None:
            raise GroupingAlreadyExistsException(
                f"A grouping already exists for workflow {workflow.workflow_id} "
                f"and function {request.function_definition_id}."
            ) from None
        raise

    runner_input = PythonGroupInput(
        runtime_name="python",
        runner_name="group",
        grouping_id=grouping.grouping_id,
    )
    dispatch_grouping_runner(
        db,
        dispatcher,
        grouping.grouping_id,
        job_id,
        runner_input,
    )
    return GroupOperationAccepted(
        job_id=job_id,
        grouping=query_grouping(db, current_user, grouping.grouping_id),
    )
