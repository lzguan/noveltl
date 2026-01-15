from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from . import schemas
from .service import query_all_languages, query_language_by_code

router = APIRouter()

@router.get('/languages/{language_code}', response_model=schemas.Language)
def read_language_by_code(
        db : Annotated[Session, Depends(get_db)],
        language_code : str
    ):
    """
    Retrieves a language by its code.

    Args:
        db: Database session.
        language_code: The code of the language to retrieve.

    Returns:
        The Language object corresponding to the given code.

    Raises:
        LanguageNotFoundException: If no language with the given code is found.
    """
    return query_language_by_code(db, language_code)

@router.get('/languages', response_model=list[schemas.Language])
def read_all_languages(
        db : Annotated[Session, Depends(get_db)]
    ):
    """
    Retrieves all languages in the database.

    Args:
        db: Database session.

    Returns:
        A list of all Language objects in the database.
    """
    return query_all_languages(db)
