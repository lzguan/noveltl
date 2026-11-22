"""
Services related to languages.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from src.languages.exceptions import LanguageNotFoundException
from src.languages.models import Language


async def query_language_by_code(db: AsyncSession, language_code: str) -> Language:
    """
    Finds language with corresponding language_code in database.

    Args:
        db: Database from which we are querying.
        language_code: code of language we are trying to obtain.

    Raises:
        LanguageNotFoundException: language code not found in database.
    """
    q = select(Language).where(Language.language_code == language_code)
    result = await db.execute(q)
    try:
        ret = result.scalar_one()
    except NoResultFound as e:
        raise LanguageNotFoundException from e
    return ret


async def query_all_languages(db: AsyncSession) -> Sequence[Language]:
    """
    Queries all languages in the database.

    Args:
        db: Database from which we are querying.

    Returns:
        List of all languages in the database.
    """
    q = select(Language)
    result = await db.execute(q)
    return result.scalars().all()
