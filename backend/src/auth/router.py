"""
Router endpoints for auth.

Todo: Come up with a proper api.
"""

import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..database import get_db
from ..exceptions import DataTooLongException, InsufficientPermissionsException
from . import schemas
from .config import ACCESS_TOKEN_EXPIRE_MINUTES
from .dependencies import get_current_user, get_optional_user
from .exceptions import UserAuthenticationFailedException, UserNameDuplicateException, UserNotFoundException
from .service import authenticate_user, insert_user, query_user_by_user_name, remove_user
from .utils import create_access_token

router = APIRouter()

@router.post(
    "/token",
    response_model=schemas.Token
)
async def login_for_access_token(
        form_data : Annotated[OAuth2PasswordRequestForm, Depends()],
        db : Annotated[Session, Depends(get_db)]
    ):
    """
    Verifies a client's login request and returns a token if it succeeds.

    Args:
        db: Database dependency.
        form_data: OAuth2PasswordRequestForm dependency.
    """
    try:
        user = authenticate_user(db, form_data.username, form_data.password)
    except UserNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
            headers={"WWW-Authenticate" : "Bearer"}
        ) from e
    except UserAuthenticationFailedException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password does not match.",
            headers={"WWW-Authenticate" : "Bearer"}
        ) from e
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        {"sub" : user.user_name},
        access_token_expires
    )
    return schemas.Token(access_token=access_token, token_type='bearer')

@router.post(
    "/register",
    response_model=schemas.User
)
async def register_user(
        request : schemas.CreateUser,
        db :  Annotated[Session, Depends(get_db)],
        current_user : Annotated[schemas.User | None, Depends(get_optional_user)]
    ):
    """
    Endpoint for registering a new user. Client with registration request must not be logged in.

    Args:
        request: Create user request.
        db: Database dependency.
        current_user: Optional user dependency. Should be None for this function to succeed.
    """
    if current_user is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User already logged in. Log out before registering as new user."
        )
    try:
        new_user = insert_user(db, None, request)
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cannot create admin account."
        ) from e
    except UserNameDuplicateException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this username already exists."
        ) from e
    except DataTooLongException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Some field too long."
        ) from e
    return new_user

@router.post(
    "/users",
    response_model=schemas.User
)
async def create_user(
        request : schemas.CreateUser,
        db : Annotated[Session, Depends(get_db)],
        current_user : Annotated[schemas.User, Depends(get_current_user)]
    ):
    """
    Creates a user with metadata request, provided that the current_user has sufficient permissions.

    Args:
        db: Database dependency.
        current_user: Current user dependency. Must not be None (e.g. user must be logged in).
        request: Metadata of user to be added.
    """
    try:
        new_user = insert_user(db, current_user, request)
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Insufficient permissions to create new user." # change this to print str(e.orig) and add error messages in exceptions.
        ) from e
    except UserNameDuplicateException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this username already exists."
        ) from e
    except DataTooLongException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Some field too long."
        ) from e
    return new_user

@router.get(
    "/users/me",
    response_model=schemas.User
)
async def read_user_me(
        current_user : Annotated[schemas.User, Depends(get_current_user)]
    ):
    """
    Return the current logged in user.

    Args:
        current_user: Current user dependency.
    """
    return current_user

@router.get(
    "/users/{userName}",
    response_model=schemas.User
)
async def read_user(
        user_name : Annotated[str, Path(alias="userName")],
        db : Annotated[Session, Depends(get_db)]
    ):
    """
    Get user by username.

    Args:
        user_name: Username of user.
        db: Database dependency.
    """
    try:
        user = query_user_by_user_name(db, user_name)
    except UserNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
            headers={"WWW-Authenticate" : "Bearer"}
        ) from e
    return user

@router.delete("/users/me", response_model=schemas.DeleteUserStatus)
async def delete_user_me(
        db : Annotated[Session, Depends(get_db)],
        current_user : Annotated[schemas.User, Depends(get_current_user)]
    ):
    """
    Delete the user currently logged in.
    """
    try:
        stat = remove_user(db, current_user, current_user.user_id)
    except UserNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {current_user.user_id} (username {current_user.user_name}) not found."
        ) from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error."
        ) from e
    return stat

@router.delete(
    '/users/{userId}',
    response_model=schemas.DeleteUserStatus
)
async def delete_user(
        user_id : Annotated[uuid.UUID, Path(alias="userId")],
        db : Annotated[Session, Depends(get_db)],
        current_user : Annotated[schemas.User, Depends(get_current_user)]
    ):
    """
    Delete the user with user_id if the current user has sufficient permissions to perform this action. Throw an exception if the user currently logged in has insufficient permissions.
    """
    try:
        stat = remove_user(db, current_user, user_id)
    except UserNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found."
        ) from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current user does not have permission to delete this user."
        ) from e
    return stat
