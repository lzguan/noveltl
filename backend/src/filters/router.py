from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..auth.models import User
from ..database import get_db
from ..novels.exceptions import RevisionTextOutdatedException
from . import service
from .exceptions import (
    FilterNotFoundException,
    InstanceContextValidationException,
    InstanceValidationException,
    OptionsValidationException,
)
from .schemas import InstanceContextOptions, InstanceOptions
from .service import SchemaInfo

router = APIRouter()


@router.get("/filters/schemas", response_model=dict[str, SchemaInfo])
def read_filter_schemas():
    """
    Retrieves the schemas for all registered filters, including the instance, context, and options schemas for each filter.

    Returns:
        A dictionary mapping filter names to their schema information.
    """
    return service.query_schemas()


@router.post("/filters/{filter_name}/flag-instances", response_model=list[Any])
def read_flagged_instances(
    filter_name: str,
    options: dict[Any, Any],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Flags instances using a specified filter and options.

    Args:
        filter_name: The name of the filter to use.
        options: The options for flagging instances, which will be validated against the filter's schema.
        db: Database session for any necessary database access during filtering.
        current_user: The user making the request, which may be relevant for certain filters.
    """
    try:
        return service.flag_instances(db, current_user, filter_name, options)
    except FilterNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except OptionsValidationException as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/filters/{filter_name}/get-contexts", response_model=list[Any])
def read_contexts(
    filter_name: str,
    body: InstanceOptions,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Retrieves contexts for a list of instances using a specified filter and options.

    Args:
        filter_name: The name of the filter to use.
        instances: The list of instances to retrieve contexts for. Each instance will be validated against the filter's instance schema.
        options: The options for retrieving contexts, which will be validated against the filter's schema.
        db: Database session for any necessary database access during context retrieval.
        current_user: The user making the request, which may be relevant for certain filters.
    """
    instances = body.instances
    options = body.options
    try:
        return service.get_contexts(db, current_user, filter_name, instances, options)
    except FilterNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except OptionsValidationException as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except InstanceValidationException as e:
        raise HTTPException(status_code=400, detail=f"Instance validation error: {e}") from e


@router.post("/filters/{filter_name}/decide-instances", response_model=list[bool])
def read_decisions(
    filter_name: str,
    body: InstanceContextOptions,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Decides whether instances pass a filter in given contexts using specified options.

    Args:
        filter_name: The name of the filter to use.
        body: An InstanceContextOptions object containing the list of instance-context pairs and the options for deciding instances. Each instance and context will be validated against the filter's schemas.
        db: Database session for any necessary database access during the decision process.
        current_user: The user making the request, which may be relevant for certain filters.
    """
    instance_contexts = body.instance_contexts
    options = body.options
    try:
        return service.decide_instances(db, current_user, filter_name, instance_contexts, options)
    except FilterNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except OptionsValidationException as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except InstanceContextValidationException as e:
        raise HTTPException(status_code=400, detail=f"Instance/context validation error: {e}") from e
    except RevisionTextOutdatedException as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/filters/{filter_name}/apply", status_code=204)
def apply_filter(
    filter_name: str,
    body: InstanceOptions,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Applies a filter to a label group for a list of instances using specified options.

    Args:
        filter_name: The name of the filter to apply.
        body: An InstanceOptions object containing the list of instances and the options for applying the filter. Each instance will be validated against the filter's instance schema, and the options will be validated against the filter's apply filter options schema.
        db: Database session for any necessary database access during filter application.
        current_user: The user making the request, which may be relevant for certain filters.
    """
    instances = body.instances
    options = body.options
    try:
        service.apply_filter(db, current_user, filter_name, instances, options)
    except FilterNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except OptionsValidationException as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except InstanceValidationException as e:
        raise HTTPException(status_code=400, detail=f"Instance validation error: {e}") from e
    except RevisionTextOutdatedException as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
