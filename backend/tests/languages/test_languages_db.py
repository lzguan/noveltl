import pytest
from sqlalchemy.exc import IntegrityError, DataError, NoResultFound
from src.languages.models import Language
from sqlalchemy.orm import Session
from sqlalchemy import select
from psycopg2.errors import Error as Psycopg2Error
from psycopg2 import errorcodes

def test_language_creation(test_db : Session):
    # Create a language
    lang = Language(language_name="English", language_code="en")
    test_db.add(lang)
    test_db.commit()
    # Query the language back
    queried_lang = test_db.execute(select(Language).where(Language.language_id == lang.language_id)).scalar_one()
    assert queried_lang is not None
    assert queried_lang.language_name == "English"
    assert queried_lang.language_code == "en"

    lang2 = Language(language_name="French", language_code="fr")
    test_db.add(lang2)
    test_db.commit()
    queried_lang2 = test_db.execute(select(Language).where(Language.language_id == lang2.language_id)).scalar_one()
    assert queried_lang2 is not None
    assert queried_lang2.language_name == "French"
    assert queried_lang2.language_code == "fr"

    # Query all languages
    all_languages = test_db.execute(select(Language)).scalars().all()
    assert len(all_languages) == 2

def test_language_unique_constraints(test_db : Session):
    # Create a language
    lang1 = Language(language_name="English", language_code="en")
    test_db.add(lang1)
    test_db.commit()

    # Attempt to create another language with the same name
    lang2 = Language(language_name="English", language_code="fr")
    test_db.add(lang2)
    with pytest.raises(IntegrityError) as e:
        test_db.commit()
    assert isinstance(e.value.orig, Psycopg2Error)
    assert e.value.orig.pgcode == errorcodes.UNIQUE_VIOLATION  # Unique violation
    test_db.rollback()

    # Attempt to create another language with the same code
    lang3 = Language(language_name="French", language_code="en")
    test_db.add(lang3)
    with pytest.raises(IntegrityError) as e:
        test_db.commit()
    assert isinstance(e.value.orig, Psycopg2Error)
    assert e.value.orig.pgcode == errorcodes.UNIQUE_VIOLATION  # Unique violation
    test_db.rollback()

def test_language_length_constraints(test_db : Session):
    # Language name exceeding 31 characters
    long_name = "L" * 32
    lang1 = Language(language_name=long_name, language_code="xx")
    test_db.add(lang1)
    with pytest.raises(DataError) as e:
        test_db.commit()
    assert isinstance(e.value.orig, Psycopg2Error)
    assert e.value.orig.pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION  # String data right truncation
    test_db.rollback()

    # Language code exceeding 2 characters
    long_code = "xxx"
    lang2 = Language(language_name="TestLang", language_code=long_code)
    test_db.add(lang2)
    with pytest.raises(DataError) as e:
        test_db.commit()
    assert isinstance(e.value.orig, Psycopg2Error)
    assert e.value.orig.pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION  # String data right truncation
    test_db.rollback()

    # Language code less than 2 characters
    short_code = "x"
    lang3 = Language(language_name="TestLang2", language_code=short_code)
    test_db.add(lang3)
    with pytest.raises(IntegrityError) as e:
        test_db.commit()
    assert isinstance(e.value.orig, Psycopg2Error)
    assert e.value.orig.pgcode == errorcodes.CHECK_VIOLATION  # Check violation
    test_db.rollback()
    with pytest.raises(NoResultFound):
        _ = test_db.execute(select(Language).where(Language.language_name == "TestLang2")).scalar_one()

    # language_name and language_code at maximum length should succeed
    max_name = "L" * 31
    max_code = "XX"
    lang4 = Language(language_name=max_name, language_code=max_code)
    test_db.add(lang4)
    test_db.commit()
    queried_lang4 = test_db.execute(select(Language).where(Language.language_id == lang4.language_id)).scalar_one()
    assert queried_lang4 is not None
    assert queried_lang4.language_name == max_name
    assert queried_lang4.language_code == max_code

def test_cannot_delete_language_in_use(test_db : Session, sample_novels : list):
    # sample_novels fixture creates novels with languages
    # Attempt to delete a language that is in use
    lang_in_use = test_db.execute(select(Language).where(Language.language_name == "English")).scalar_one()
    test_db.delete(lang_in_use)
    with pytest.raises(IntegrityError) as e:
        test_db.commit()
    assert isinstance(e.value.orig, Psycopg2Error)
    assert e.value.orig.pgcode == errorcodes.FOREIGN_KEY_VIOLATION  # Foreign key violation
    test_db.rollback()