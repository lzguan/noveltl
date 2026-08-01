from uuid import UUID

from sqlalchemy import Boolean, Float, Integer, and_, cast, exists, or_, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session, aliased, defer

from src.auth.models import User
from src.filters.data_types import BoolField, IntField, Schema, StringField, data_adapter
from src.filters.exceptions import FunctionNotFoundException, InstanceNotFoundException, WorkflowNotFoundException
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
from src.filters.schemas import FunctionDefinitionMeta, InstanceQuery, validate_frame_workflow


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
    query = (
        query.limit(limit)
        .order_by(FunctionDefinition.function_definition_id)
        .options(defer(FunctionDefinition.function_definition))
    )
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
    q = select(Instance).where(Instance.workflow_id == workflow_id)
    q = instance_mod_access_select(q, current_user)
    if cursor is not None:
        q = q.where(Instance.instance_id > cursor)
    q = q.order_by(Instance.instance_id).limit(limit)
    return list(db.execute(q).scalars().all())


def query_instances_of_workflow_advanced(db: Session, current_user: User, request: InstanceQuery) -> list[Instance]:
    # Validate the workflow and schema
    workflow_id = request.frame.workflow_id
    try:
        workflow = db.execute(
            workflow_mod_access_select(select(Workflow).where(Workflow.workflow_id == workflow_id), current_user)
        ).scalar_one()
    except NoResultFound as e:
        raise WorkflowNotFoundException(f"Workflow with ID {workflow_id} not found or not accessible.") from e

    instance_query = select(Instance).where(Instance.workflow_id == workflow_id)

    # Grouping filters
    group_select = (
        select(Grouping, FunctionDefinition)
        .where(Grouping.workflow_id == workflow_id)
        .where(Grouping.grouping_id.in_([gf.grouping_id for gf in request.frame.group_filters]))
        .join(FunctionDefinition, Grouping.function_definition_id == FunctionDefinition.function_definition_id)
    )
    groups = db.execute(group_select).all()
    if len(groups) != len(request.frame.group_filters):
        missing_ids = {gf.grouping_id for gf in request.frame.group_filters} - {g.grouping_id for g in groups}
        raise ValueError(f"Grouping IDs not found in workflow {workflow_id}: {missing_ids}")

    _group_map = {g.grouping_id: g for g in groups}
    _group_map_2 = {g.grouping_id: g for g in request.frame.group_filters}
    group_map = {g.grouping_id: (g, _group_map_2[g.grouping_id]) for g in groups}
    orval = None
    for grouping_id, (g_and_f, group_filter) in group_map.items():
        if g_and_f.grouping_status != GroupingStatus.COMPLETE:
            raise ValueError(f"Grouping {grouping_id} is not complete and cannot be used for filtering.")
        function = function_adapter.validate_python(g_and_f.function_definition)
        output_type = function.signature.output
        if not isinstance(output_type, (StringField, IntField, BoolField)):
            raise ValueError(f"Grouping function {g_and_f.function_definition_id} must return string, int, or bool.")
        vals = [gf.value for gf in group_filter.values]
        if isinstance(output_type, StringField):
            if not all(isinstance(v, str) for v in vals):
                raise ValueError(
                    f"Grouping function {g_and_f.function_definition_id} returns string, but values are not all strings."
                )
            g_alias = aliased(GroupAssignment)
            instance_query = instance_query.join(g_alias, g_alias.instance_id == Instance.instance_id)
            if orval is None:
                orval = or_(and_(g_alias.grouping_id == grouping_id, g_alias.function_value.in_(vals)))
            else:
                orval = or_(orval, and_(g_alias.grouping_id == grouping_id, g_alias.function_value.in_(vals)))
    if orval is not None:
        instance_query = instance_query.where(orval)
    # Sorting + cursor handling
    schema = Schema.model_validate(workflow.schema)
    validate_frame_workflow(request.frame, schema)

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
        for key, asc in request.frame.sort_keys:
            if schema.fields[key].type == "string":
                t = Instance.value["fields"][key]["value"].astext
            elif schema.fields[key].type == "int":
                t = cast(Instance.value["fields"][key]["value"], Integer)
            elif schema.fields[key].type == "float":
                t = cast(Instance.value["fields"][key]["value"], Float)
            elif schema.fields[key].type == "bool":
                t = cast(Instance.value["fields"][key]["value"], Boolean)
            else:
                raise ValueError(f"Unsupported sort key type: {schema.fields[key].type}")

            if asc:
                instance_query = instance_query.where(t > data.fields[key].value).order_by(t.asc())
            else:
                instance_query = instance_query.where(t < data.fields[key].value).order_by(t.desc())
        if len(request.frame.sort_keys) > 0:
            instance_query = instance_query.where(Instance.instance_id != request.cursor)
        else:
            instance_query = instance_query.where(Instance.instance_id > request.cursor)
    instance_query = instance_query.order_by(Instance.instance_id.asc())
    instance_query = instance_query.limit(request.limit)
    instance_query = instance_mod_access_select(instance_query, current_user)

    return list(db.execute(instance_query).scalars().all())
