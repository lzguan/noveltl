"""
Services related to languages.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from . import models
from .exceptions import LanguageNotFoundException


def query_language_by_id(db : Session, language_id : int) -> models.Language:
    """
    Finds language with corresponding language_id in database.

    Args:
        db: Database from which we are querying.
        language_id: id of language we are trying to obtain.

    Raises:
        LanguageNotFoundException: language id not found in database.
    """
    q = select(models.Language).where(models.Language.language_id == language_id)
    result = db.execute(q)
    try:
        ret = result.scalar_one()
    except NoResultFound as e:
        raise LanguageNotFoundException from e
    return ret

def query_language_by_code(db : Session, language_code : str) -> models.Language:
    """
    Finds language with corresponding language_code in database.

    Args:
        db: Database from which we are querying.
        language_code: code of language we are trying to obtain.

    Raises:
        LanguageNotFoundException: language code not found in database.
    """
    q = select(models.Language).where(models.Language.language_code == language_code)
    result = db.execute(q)
    try:
        ret = result.scalar_one()
    except NoResultFound as e:
        raise LanguageNotFoundException from e
    return ret

def query_all_languages(db : Session) -> Sequence[models.Language]:
    """
    Queries all languages in the database.

    Args:
        db: Database from which we are querying.

    Returns:
        List of all languages in the database.
    """
    q = select(models.Language)
    result = db.execute(q)
    return result.scalars().all()
