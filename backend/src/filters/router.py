from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_db
from src.filters.dependencies import get_dispatcher
from src.filters.dispatch.dispatcher import RunnerDispatcher
from src.filters.exceptions import (
    FunctionAlreadyExistsException,
    FunctionNotFoundException,
    GroupingAlreadyExistsException,
    GroupingNotFoundException,
    GroupingNotReadyException,
    InstanceNotFoundException,
    InvalidInstanceQueryException,
    InvalidRunnerRequestException,
    RunnerEnqueueFailedException,
    WorkflowNotFoundException,
    WorkflowNotReadyException,
)
from src.filters.models import GroupingStatus, WorkflowStatus, WorkflowUseCase
from src.filters.schemas import (
    CreateFunctionDefinitionRequest,
    FunctionDefinitionMeta,
    FunctionDefinitionResponse,
    GroupingResponse,
    GroupingSummary,
    GroupOperationAccepted,
    GroupValueCount,
    InstanceQuery,
    InstanceQueryResult,
    InstanceResponse,
    PythonFilterRequest,
    PythonGroupRequest,
    PythonLabelSourceRequest,
    PythonMapRequest,
    RenameWorkflowRequest,
    WorkflowOperationAccepted,
    WorkflowResponse,
    WorkflowSummary,
)
from src.filters.service import (
    create_function_definition,
    query_function,
    query_functions,
    query_grouping,
    query_grouping_values,
    query_groupings,
    query_instances_of_workflow,
    query_instances_of_workflow_advanced,
    query_workflow,
    query_workflows,
    rename_workflow,
    run_filter,
    run_group,
    run_label_source,
    run_map,
)
from src.schemas import DetailHTTPErrorResponse

router = APIRouter(prefix="/filters", tags=["filters"])

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.get("/functions", response_model=list[FunctionDefinitionMeta])
def read_functions(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
    namespace: str | None = None,
    limit: Limit = 50,
    cursor: UUID | None = None,
) -> list[FunctionDefinitionMeta]:
    """List saved function definitions."""
    return query_functions(db, current_user, search, namespace, limit, cursor)


@router.get(
    "/functions/{functionDefinitionId}",
    response_model=FunctionDefinitionResponse,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def read_function(
    function_definition_id: Annotated[UUID, Path(alias="functionDefinitionId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FunctionDefinitionResponse:
    """Return one saved function definition."""
    try:
        return FunctionDefinitionResponse.model_validate(query_function(db, current_user, function_definition_id))
    except FunctionNotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc) or "Function definition not found.",
        ) from exc


@router.get("/workflows", response_model=list[WorkflowSummary])
def read_workflows(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    novel_id: Annotated[UUID | None, Query(alias="novelId")] = None,
    label_group_id: Annotated[UUID | None, Query(alias="labelGroupId")] = None,
    use_case: Annotated[WorkflowUseCase | None, Query(alias="useCase")] = None,
    workflow_status: Annotated[WorkflowStatus | None, Query(alias="status")] = None,
    search: str | None = None,
    limit: Limit = 50,
    cursor: UUID | None = None,
) -> list[WorkflowSummary]:
    """List workflows accessible to the current user."""
    workflows = query_workflows(
        db,
        current_user,
        novel_id,
        label_group_id,
        use_case,
        workflow_status,
        search,
        limit,
        cursor,
    )
    return [WorkflowSummary.model_validate(workflow) for workflow in workflows]


@router.get(
    "/workflows/{workflowId}",
    response_model=WorkflowResponse,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def read_workflow(
    workflow_id: Annotated[UUID, Path(alias="workflowId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WorkflowResponse:
    """Return one workflow with its permission scope and instance count."""
    try:
        return query_workflow(db, current_user, workflow_id)
    except WorkflowNotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc) or "Workflow not found.",
        ) from exc


@router.get(
    "/workflows/{workflowId}/instances",
    response_model=list[InstanceResponse],
    responses={
        404: {"model": DetailHTTPErrorResponse},
        409: {"model": DetailHTTPErrorResponse},
    },
)
def read_workflow_instances(
    workflow_id: Annotated[UUID, Path(alias="workflowId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Limit = 50,
    cursor: UUID | None = None,
) -> list[InstanceResponse]:
    """List instances of one completed workflow."""
    try:
        instances = query_instances_of_workflow(db, current_user, workflow_id, limit, cursor)
    except WorkflowNotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc) or "Workflow not found.",
        ) from exc
    except WorkflowNotReadyException as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc) or "Workflow is not ready.",
        ) from exc
    return [InstanceResponse.model_validate(instance) for instance in instances]


@router.post(
    "/instances/query",
    response_model=list[InstanceQueryResult],
    responses={
        400: {"model": DetailHTTPErrorResponse},
        404: {"model": DetailHTTPErrorResponse},
        409: {"model": DetailHTTPErrorResponse},
    },
)
def read_instances_advanced(
    request: InstanceQuery,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[InstanceQueryResult]:
    """Query instances with grouping filters and scalar sort keys."""
    try:
        return query_instances_of_workflow_advanced(db, current_user, request)
    except (WorkflowNotFoundException, GroupingNotFoundException, InstanceNotFoundException) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc) or "Filter resource not found.",
        ) from exc
    except (WorkflowNotReadyException, GroupingNotReadyException) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc) or "Filter resource is not ready.",
        ) from exc
    except InvalidInstanceQueryException as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/workflows/{workflowId}/groupings",
    response_model=list[GroupingSummary],
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def read_workflow_groupings(
    workflow_id: Annotated[UUID, Path(alias="workflowId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    grouping_status: Annotated[GroupingStatus | None, Query(alias="status")] = None,
    limit: Limit = 50,
    cursor: UUID | None = None,
) -> list[GroupingSummary]:
    """List groupings attached to one workflow."""
    try:
        groupings = query_groupings(db, current_user, workflow_id, grouping_status, limit, cursor)
    except WorkflowNotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc) or "Workflow not found.",
        ) from exc
    return [GroupingSummary.model_validate(grouping) for grouping in groupings]


@router.get(
    "/groupings/{groupingId}",
    response_model=GroupingResponse,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def read_grouping(
    grouping_id: Annotated[UUID, Path(alias="groupingId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> GroupingResponse:
    """Return one grouping with derived output metadata."""
    try:
        return query_grouping(db, current_user, grouping_id)
    except GroupingNotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc) or "Grouping not found.",
        ) from exc


@router.get(
    "/groupings/{groupingId}/values",
    response_model=list[GroupValueCount],
    responses={
        400: {"model": DetailHTTPErrorResponse},
        404: {"model": DetailHTTPErrorResponse},
        409: {"model": DetailHTTPErrorResponse},
    },
)
def read_grouping_values(
    grouping_id: Annotated[UUID, Path(alias="groupingId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> list[GroupValueCount]:
    """List distinct values and counts for one completed grouping."""
    try:
        return query_grouping_values(db, current_user, grouping_id, search, limit, offset)
    except GroupingNotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc) or "Grouping not found.",
        ) from exc
    except GroupingNotReadyException as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc) or "Grouping is not ready.",
        ) from exc
    except InvalidInstanceQueryException as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/functions",
    response_model=FunctionDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": DetailHTTPErrorResponse}},
    operation_id="create_filter_function",
)
def create_filter_function(
    request: CreateFunctionDefinitionRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FunctionDefinitionResponse:
    """Save an immutable function definition in the shared registry."""
    try:
        return create_function_definition(db, request)
    except FunctionAlreadyExistsException as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc) or "Function definition already exists.",
        ) from exc


@router.patch(
    "/workflows/{workflowId}",
    response_model=WorkflowResponse,
    responses={404: {"model": DetailHTTPErrorResponse}},
    operation_id="rename_filter_workflow",
)
def rename_filter_workflow(
    workflow_id: Annotated[UUID, Path(alias="workflowId")],
    request: RenameWorkflowRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WorkflowResponse:
    """Rename or clear the name of an accessible workflow."""
    try:
        return rename_workflow(db, current_user, workflow_id, request)
    except WorkflowNotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc) or "Workflow not found.",
        ) from exc


@router.post(
    "/runners/python/label-source",
    response_model=WorkflowOperationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        404: {"model": DetailHTTPErrorResponse},
        503: {"model": DetailHTTPErrorResponse},
    },
    operation_id="run_python_label_source",
)
def run_python_label_source(
    request: PythonLabelSourceRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    dispatcher: Annotated[RunnerDispatcher, Depends(get_dispatcher)],
) -> WorkflowOperationAccepted:
    """Create and enqueue a workflow from the current labels in a group."""
    try:
        return run_label_source(db, current_user, dispatcher, request)
    except WorkflowNotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc) or "Label group not found or not accessible.",
        ) from exc
    except RunnerEnqueueFailedException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc) or "Runner publication failed.",
        ) from exc


@router.post(
    "/runners/python/map",
    response_model=WorkflowOperationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": DetailHTTPErrorResponse},
        404: {"model": DetailHTTPErrorResponse},
        409: {"model": DetailHTTPErrorResponse},
        503: {"model": DetailHTTPErrorResponse},
    },
    operation_id="run_python_map",
)
def run_python_map(
    request: PythonMapRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    dispatcher: Annotated[RunnerDispatcher, Depends(get_dispatcher)],
) -> WorkflowOperationAccepted:
    """Create and enqueue a mapped workflow."""
    try:
        return run_map(db, current_user, dispatcher, request)
    except (WorkflowNotFoundException, FunctionNotFoundException) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc) or "Filter resource not found.",
        ) from exc
    except WorkflowNotReadyException as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc) or "Workflow is not ready.",
        ) from exc
    except InvalidRunnerRequestException as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RunnerEnqueueFailedException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc) or "Runner publication failed.",
        ) from exc


@router.post(
    "/runners/python/filter",
    response_model=WorkflowOperationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": DetailHTTPErrorResponse},
        404: {"model": DetailHTTPErrorResponse},
        409: {"model": DetailHTTPErrorResponse},
        503: {"model": DetailHTTPErrorResponse},
    },
    operation_id="run_python_filter",
)
def run_python_filter(
    request: PythonFilterRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    dispatcher: Annotated[RunnerDispatcher, Depends(get_dispatcher)],
) -> WorkflowOperationAccepted:
    """Create and enqueue a filtered workflow."""
    try:
        return run_filter(db, current_user, dispatcher, request)
    except (WorkflowNotFoundException, FunctionNotFoundException) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc) or "Filter resource not found.",
        ) from exc
    except WorkflowNotReadyException as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc) or "Workflow is not ready.",
        ) from exc
    except InvalidRunnerRequestException as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RunnerEnqueueFailedException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc) or "Runner publication failed.",
        ) from exc


@router.post(
    "/runners/python/group",
    response_model=GroupOperationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": DetailHTTPErrorResponse},
        404: {"model": DetailHTTPErrorResponse},
        409: {"model": DetailHTTPErrorResponse},
        503: {"model": DetailHTTPErrorResponse},
    },
    operation_id="run_python_group",
)
def run_python_group(
    request: PythonGroupRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    dispatcher: Annotated[RunnerDispatcher, Depends(get_dispatcher)],
) -> GroupOperationAccepted:
    """Create and enqueue grouping assignments for a workflow."""
    try:
        return run_group(db, current_user, dispatcher, request)
    except (WorkflowNotFoundException, FunctionNotFoundException) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc) or "Filter resource not found.",
        ) from exc
    except (WorkflowNotReadyException, GroupingAlreadyExistsException) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc) or "Grouping operation conflicts with current state.",
        ) from exc
    except InvalidRunnerRequestException as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RunnerEnqueueFailedException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc) or "Runner publication failed.",
        ) from exc
