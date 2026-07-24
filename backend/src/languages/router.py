from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from src.database import get_db
from src.languages.exceptions import LanguageNotFoundException
from src.languages.schemas import Language
from src.languages.service import query_all_languages, query_language_by_code

router = APIRouter()


@router.get("/languages/{languageCode}", response_model=Language)
def read_language_by_code(
    language_code: Annotated[str, Path(alias="languageCode")], db: Annotated[Session, Depends(get_db)]
):
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


@router.get("/languages", response_model=list[Language])
def read_all_languages(db: Annotated[Session, Depends(get_db)]):
    """
    Retrieves all languages in the database.

    Args:
        db: Database session.
    """
    return query_all_languages(db)
