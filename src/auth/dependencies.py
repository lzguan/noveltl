from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from typing import Annotated
from .config import *
from .schemas import *
from .service import *
from ..database import get_db
import jwt
from jwt.exceptions import InvalidTokenError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

async def get_optional_user(
        db : Annotated[Session, Depends(get_db)],
        token : Annotated[str, Depends(oauth2_scheme_optional)]
    ) -> schemas.User | None:
    """
    Get the current user as a Pydantic schema from a JSON web token, or return None if there is no current logged in user.

    Args:
        db: Database we are connected to.
        token: JSON web token to process.
    """
    if token is None:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception
    try:
        user = query_user_by_user_name(db, username)
    except UserNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
    except UserTooManyFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="More than one user with this username found.."
        )
    return user

async def get_current_user(
        user : Annotated[schemas.User | None, Depends(get_optional_user)]
    ) -> schemas.User:
    """
    Does the same as get_optional_user, except throws an HTTPException if there is no user currently logged in.

    Args:
        user: User dependency from get_optional_user.
    """
    if user is None:
        raise credentials_exception
    return user