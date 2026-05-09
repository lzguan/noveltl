import pytest
from sqlalchemy.orm import Session

from src.languages import models
from src.languages.exceptions import LanguageNotFoundException
from src.languages.service import query_all_languages, query_language_by_code


@pytest.fixture(scope="function")
def language_session_test(test_db: Session) -> dict[str, models.Language]:
    # Setup: add some languages
    lang1 = models.Language(language_name="English", language_code="en")
    lang2 = models.Language(language_name="French", language_code="fr")
    test_db.add_all([lang1, lang2])
    test_db.commit()
    return {"en": lang1, "fr": lang2}


def test_query_language_by_id(test_db: Session, language_session_test: dict[str, models.Language]):
    lang_en = language_session_test["en"]
    queried_lang = query_language_by_code(test_db, language_session_test["en"].language_code)
    assert queried_lang.language_name == "English"
    assert queried_lang.language_code == "en"
    assert queried_lang.language_code == lang_en.language_code

    lang_fr = language_session_test["fr"]
    queried_lang = query_language_by_code(test_db, language_session_test["fr"].language_code)
    assert queried_lang.language_name == "French"
    assert queried_lang.language_code == "fr"
    assert queried_lang.language_code == lang_fr.language_code

    with pytest.raises(LanguageNotFoundException):
        query_language_by_code(test_db, "xx")  # Non-existent code


def test_query_language_by_code(test_db: Session, language_session_test: dict[str, models.Language]):
    queried_lang = query_language_by_code(test_db, "en")
    assert queried_lang.language_name == "English"
    assert queried_lang.language_code == "en"

    queried_lang = query_language_by_code(test_db, "fr")
    assert queried_lang.language_name == "French"
    assert queried_lang.language_code == "fr"

    with pytest.raises(LanguageNotFoundException):
        query_language_by_code(test_db, "xx")  # Non-existent code


def test_query_all_languages(test_db: Session, language_session_test: dict[str, models.Language]):
    queried_languages = query_all_languages(test_db)
    assert len(queried_languages) == len(language_session_test)
    names_and_codes = {(lang.language_name, lang.language_code) for lang in queried_languages}
    expected_names_and_codes = {(lang.language_name, lang.language_code) for _, lang in language_session_test.items()}
    assert len(names_and_codes.symmetric_difference(expected_names_and_codes)) == 0
