from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound, MultipleResultsFound, IntegrityError, DataError
from . import models, schemas
from .utils import *
from .exceptions import *
from .constants import UserType
from psycopg2 import errorcodes

def query_user_by_user_name(
        db : Session, 
        user_name : str
    ) -> models.User:
    """
    Finds exactly one user in the database with user_name, or raises an exception

    Args:
        db: Database from which we are querying.
        user_name: Username of the user we are querying.
    
    Raises:
        UserNotFoundException: No user with username user_name found in db.
        UserTooManyFoundException: More than one user with user_name found in db.
    """
    q = select(models.User).where(models.User.user_name == user_name)
    try:
        result = db.execute(q)
        result_user = result.scalar_one()
    except NoResultFound as e:
        raise UserNotFoundException
    except MultipleResultsFound as e:
        raise UserTooManyFoundException
    return result_user

def query_user_by_id(
        db : Session, 
        user_id : int
    ) -> models.User:
    """
    Finds exactly one user in the database with user_id, or raises an exception

    Args:
        db: Database from which we are querying.
        user_id: id of the user we are querying.
    
    Raises:
        UserNotFoundException: No user with user id user_id found in db.
        UserTooManyFoundException: More than one user with user_id found in db.
    """
    q = select(models.User).where(models.User.user_id == user_id)
    try:
        result = db.execute(q)
        result_user = result.scalar_one()
    except NoResultFound as e:
        raise UserNotFoundException
    except MultipleResultsFound as e:
        raise UserTooManyFoundException
    return result_user

def authenticate_user(
        db : Session, 
        user_name : str, 
        password : str
    ) -> models.User:
    """
    Authenticates a user login and returns a User object if successful.

    Args:
        db: Database holding user info.
        user_name: Username of user to authenticate.
        password: Unhashed password of user to authenticate.
    
    Raises:
        UserNotFoundException: No user with user_name found in database.
        UserTooManyFoundException: More than one user with user_name found in database.
        UserAuthenticationFailedException: Password does not match required password.
    """
    db_user = query_user_by_user_name(db, user_name)
    if not verify_password(password, db_user.user_hashed_password):
        raise UserAuthenticationFailedException
    return db_user

def insert_user(
        db : Session, 
        current_user : schemas.User | None,
        request : schemas.CreateUser
    ) -> models.User:
    """
    Inserts a new user into the database, under the assumption that the current_user is doing the insertion.

    Args:
        db: Database into which we are inserting.
        current_user: User that is performing the insert. If None, then guest is creating an account.
        request: Metadata about user to create.
    
    Raises:
        InsufficientPermissionsException: Guest cannot create ADMIN account. If a regular user is logged in, they should not be allowed to create a new user.
        UserNameDuplicateException: 
        DataTooLongException: Some field is too long.
    """
    # validate
    if current_user is None:
        if request.user_type == UserType.ADMIN:
            raise InsufficientPermissionsException
    elif current_user.user_type == UserType.USER: # if user logged in, should not allow to create
        raise InsufficientPermissionsException
    
    # add new user into db
    hashed_password = hash_password(request.user_password)
    new_user = models.User(user_name=request.user_name, user_hashed_password=hashed_password, user_type=request.user_type)
    try:
        db.add(new_user)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        pgcode = e.orig.pgcode
        if pgcode == errorcodes.UNIQUE_VIOLATION:
            raise UserNameDuplicateException
        raise UnknownError(str(e.orig))
    except DataError as e:
        db.rollback()
        pgcode = e.orig.pgcode
        if pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
            raise DataTooLongException
        raise UnknownError(str(e.orig))
    return new_user

def remove_user(db : Session, current_user : schemas.User, user_id : int) -> schemas.DeleteUserStatus:
    """
    Removes a user with user_id from the database. The user performing the remove is current_user.

    Args:
        db: Database to remove from.
        current_user: User performing the remove operation.
        user_id: id of user being removed.
    
    Raises:
        UserNotFoundException: If user_id not found in db
        UserTooManyFoundException: If more than one user with user_id found in db
        InsufficientPermissionsException: If a regular user tries to delete someone that is not themself.
    """
    delete_user = query_user_by_id(db, user_id)
    if current_user.user_type != UserType.ADMIN and user_id != current_user.user_id:
        raise InsufficientPermissionsException
    try:
        db.delete(delete_user)
        db.commit()
    except Exception as e:
        raise UnknownError(e)
    return schemas.DeleteUserStatus(status="success", detail=f"Delete user {user_id} success")