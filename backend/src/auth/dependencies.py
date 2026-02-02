from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from ..database import get_db
from . import models
from .config import ALGORITHM, SECRET_KEY
from .exceptions import UserNotFoundException
from .service import query_user_by_user_name

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

async def get_optional_user(
        db : Annotated[Session, Depends(get_db)],
        token : Annotated[str | None, Depends(oauth2_scheme_optional)]
    ) -> models.User | None:
    """
    Get the current user as a Pydantic schema from a JSON web token, or return None if there is no current logged in user.

    Args:
        db: Database we are connected to.
        token: JSON web token to process.
    """
    if token is None:
        return None
    try:
        payload : dict[str, Any] = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]) # type: ignore
        username = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    try:
        user = query_user_by_user_name(db, username)
    except UserNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        ) from e
    return user

async def get_current_user(
        user : Annotated[models.User | None, Depends(get_optional_user)]
    ) -> models.User:
    """
    Does the same as get_optional_user, except throws an HTTPException if there is no user currently logged in.

    Args:
        user: User dependency from get_optional_user.
    """
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
