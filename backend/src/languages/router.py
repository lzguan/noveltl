from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from . import schemas
from .exceptions import LanguageNotFoundException
from .service import query_all_languages, query_language_by_code

router = APIRouter()


@router.get("/languages/{language_code}", response_model=schemas.Language)
def read_language_by_code(language_code: str, db: Annotated[Session, Depends(get_db)]):
    """
    Retrieves a language by its code.

    Args:
        language_code: The code of the language to retrieve.
        db: Database session.
    """
    try:
        lang = query_language_by_code(db, language_code)
    except LanguageNotFoundException as e:
        raise HTTPException(status_code=404, detail="Language not found") from e
    return lang


@router.get("/languages", response_model=list[schemas.Language])
def read_all_languages(db: Annotated[Session, Depends(get_db)]):
    """
    Retrieves all languages in the database.

    Args:
        db: Database session.
    """
    return query_all_languages(db)
