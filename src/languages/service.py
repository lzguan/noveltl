"""
Services related to languages.
"""

from . import models
from sqlalchemy.orm import Session
from sqlalchemy import select
from .exceptions import *
from sqlalchemy.exc import NoResultFound

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
        raise LanguageNotFoundException
    return ret