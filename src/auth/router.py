from ..database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from .dependencies import *
from .service import *
from .schemas import *
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated

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
    except UserNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
            headers={"WWW-Authenticate" : "Bearer"}
        )
    except UserTooManyFoundException:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="More than one user with this username found."
        )
    except UserAuthenticationFailedException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password does not match.",
            headers={"WWW-Authenticate" : "Bearer"}
        )
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
async def create_register_user(
        request : schemas.CreateUser,
        db :  Annotated[Session, Depends(get_db)], 
        current_user : Annotated[schemas.User | None, Depends(get_optional_user)]
    ):
    """
    Endpoint for registering a new user. Client with registration request must not be logged in.

    Args:
        db: Database dependency.
        current_user: Optional user dependency. Should be None for this function to succeed.
        request: 
    """
    if current_user is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User already logged in. Log out before registering as new user."
        )
    try:
        new_user = insert_user(db, None, request)
    except InsufficientPermissionsException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cannot create admin account."
        )
    except UserNameDuplicateException:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this username already exists."
        )
    except DataTooLongException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Some field too long."
        )
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
    except InsufficientPermissionsException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Insufficient permissions to create new user." # change this to print str(e.orig) and add error messages in exceptions.
        )
    except UserNameDuplicateException:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this username already exists."
        )
    except DataTooLongException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Some field too long."
        )
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
    "/users/{user_name}",
    response_model=schemas.User
)
async def read_user(
        user_name : str,
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
    except UserNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
            headers={"WWW-Authenticate" : "Bearer"}
        )
    except UserTooManyFoundException:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="More than one user with this username found."
        )
    return user

@router.delete("/users/me", response_model=schemas.DeleteUserStatus)
async def delete_users_me(
        db : Annotated[Session, Depends(get_db)],
        current_user : Annotated[schemas.User, Depends(get_current_user)]
    ):
    """
    Delete the user currently logged in.
    """
    try:
        stat = remove_user(db, current_user, current_user.user_id)
    except UserNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {current_user.user_id} (username {current_user.user_name}) not found."
        )
    except UserTooManyFoundException:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Multiple users found with the same id."
        )
    except InsufficientPermissionsException:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error."
        )
    return stat

@router.delete(
    '/users/{user_id}', 
    response_model=schemas.DeleteUserStatus
)
async def delete_user(
        user_id : int,
        db : Annotated[Session, Depends(get_db)],
        current_user : Annotated[schemas.User, Depends(get_current_user)]
    ):
    """
    Delete the user with user_id if the current user has sufficient permissions to perform this action. Throw an exception if the user currently logged in has insufficient permissions.
    """
    try:
        stat = remove_user(db, current_user, user_id)
    except UserNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found."
        )
    except UserTooManyFoundException:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Multiple users found with the same id."
        )
    except InsufficientPermissionsException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current user does not have permission to delete this user."
        )
    return stat