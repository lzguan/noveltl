import pytest
from sqlalchemy.exc import IntegrityError, DataError, NoResultFound
from src.languages.models import Language
from sqlalchemy.orm import Session
from sqlalchemy import select
from psycopg2.errors import Error as Psycopg2Error
from psycopg2 import errorcodes

def test_language_creation(db_session : Session):
    # Create a language
    lang = Language(language_name="English", language_code="en")
    db_session.add(lang)
    db_session.commit()
    # Query the language back
    queried_lang = db_session.execute(select(Language).where(Language.language_id == lang.language_id)).scalar_one()
    assert queried_lang is not None
    assert queried_lang.language_name == "English"
    assert queried_lang.language_code == "en"

    lang2 = Language(language_name="French", language_code="fr")
    db_session.add(lang2)
    db_session.commit()
    queried_lang2 = db_session.execute(select(Language).where(Language.language_id == lang2.language_id)).scalar_one()
    assert queried_lang2 is not None
    assert queried_lang2.language_name == "French"
    assert queried_lang2.language_code == "fr"

    # Query all languages
    all_languages = db_session.execute(select(Language)).scalars().all()
    assert len(all_languages) == 2

def test_language_unique_constraints(db_session : Session):
    # Create a language
    lang1 = Language(language_name="English", language_code="en")
    db_session.add(lang1)
    db_session.commit()

    # Attempt to create another language with the same name
    lang2 = Language(language_name="English", language_code="fr")
    db_session.add(lang2)
    with pytest.raises(IntegrityError) as e:
        db_session.commit()
    assert isinstance(e.value.orig, Psycopg2Error)
    assert e.value.orig.pgcode == errorcodes.UNIQUE_VIOLATION  # Unique violation
    db_session.rollback()

    # Attempt to create another language with the same code
    lang3 = Language(language_name="French", language_code="en")
    db_session.add(lang3)
    with pytest.raises(IntegrityError) as e:
        db_session.commit()
    assert isinstance(e.value.orig, Psycopg2Error)
    assert e.value.orig.pgcode == errorcodes.UNIQUE_VIOLATION  # Unique violation
    db_session.rollback()

def test_language_length_constraints(db_session : Session):
    # Language name exceeding 31 characters
    long_name = "L" * 32
    lang1 = Language(language_name=long_name, language_code="xx")
    db_session.add(lang1)
    with pytest.raises(DataError) as e:
        db_session.commit()
    assert isinstance(e.value.orig, Psycopg2Error)
    assert e.value.orig.pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION  # String data right truncation
    db_session.rollback()

    # Language code exceeding 2 characters
    long_code = "xxx"
    lang2 = Language(language_name="TestLang", language_code=long_code)
    db_session.add(lang2)
    with pytest.raises(DataError) as e:
        db_session.commit()
    assert isinstance(e.value.orig, Psycopg2Error)
    assert e.value.orig.pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION  # String data right truncation
    db_session.rollback()

    # Language code less than 2 characters
    short_code = "x"
    lang3 = Language(language_name="TestLang2", language_code=short_code)
    db_session.add(lang3)
    with pytest.raises(IntegrityError) as e:
        db_session.commit()
    assert isinstance(e.value.orig, Psycopg2Error)
    assert e.value.orig.pgcode == errorcodes.CHECK_VIOLATION  # Check violation
    db_session.rollback()
    with pytest.raises(NoResultFound):
        _ = db_session.execute(select(Language).where(Language.language_name == "TestLang2")).scalar_one()

    # language_name and language_code at maximum length should succeed
    max_name = "L" * 31
    max_code = "XX"
    lang4 = Language(language_name=max_name, language_code=max_code)
    db_session.add(lang4)
    db_session.commit()
    queried_lang4 = db_session.execute(select(Language).where(Language.language_id == lang4.language_id)).scalar_one()
    assert queried_lang4 is not None
    assert queried_lang4.language_name == max_name
    assert queried_lang4.language_code == max_code

def test_cannot_delete_language_in_use(db_session : Session, sample_novels : list):
    # sample_novels fixture creates novels with languages
    # Attempt to delete a language that is in use
    lang_in_use = db_session.execute(select(Language).where(Language.language_name == "English")).scalar_one()
    db_session.delete(lang_in_use)
    with pytest.raises(IntegrityError) as e:
        db_session.commit()
    assert isinstance(e.value.orig, Psycopg2Error)
    assert e.value.orig.pgcode == errorcodes.FOREIGN_KEY_VIOLATION  # Foreign key violation
    db_session.rollback()