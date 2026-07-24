"""
Services related to languages.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from src.languages.exceptions import LanguageNotFoundException
from src.languages.models import Language


def query_language_by_code(db: Session, language_code: str) -> Language:
    """
    Finds language with corresponding language_code in database.

    Args:
        db: Database from which we are querying.
        language_code: code of language we are trying to obtain.

    Raises:
        LanguageNotFoundException: language code not found in database.
    """
    q = select(Language).where(Language.language_code == language_code)
    result = db.execute(q)
    try:
        ret = result.scalar_one()
    except NoResultFound as e:
        raise LanguageNotFoundException from e
    return ret


def query_all_languages(db: Session) -> Sequence[Language]:
    """
    Queries all languages in the database.

    Args:
        db: Database from which we are querying.

    Returns:
        List of all languages in the database.
    """
    q = select(Language)
    result = db.execute(q)
    return result.scalars().all()
