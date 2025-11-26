import pytest
from src.languages.service import *
from src.languages.models import Language
from sqlalchemy.orm import Session
from typing import Dict

@pytest.fixture(scope="function")
def language_session_test(db_session : Session) -> Dict[str, Language]:
    # Setup: add some languages
    lang1 = models.Language(language_name="English", language_code="en")
    lang2 = models.Language(language_name="French", language_code="fr")
    db_session.add_all([lang1, lang2])
    db_session.commit()
    return {"en": lang1, "fr": lang2}

def test_query_language_by_id(db_session : Session, language_session_test : Dict[str, Language]):
    lang_en = language_session_test['en']
    queried_lang = query_language_by_id(db_session, language_session_test['en'].language_id)
    assert queried_lang.language_name == "English"
    assert queried_lang.language_code == "en"
    assert queried_lang.language_id == lang_en.language_id

    lang_fr = language_session_test['fr']
    queried_lang = query_language_by_id(db_session, language_session_test['fr'].language_id)
    assert queried_lang.language_name == "French"
    assert queried_lang.language_code == "fr"
    assert queried_lang.language_id == lang_fr.language_id

    largest_id = max(lang.language_id for _, lang in language_session_test.items())
    with pytest.raises(LanguageNotFoundException):
        query_language_by_id(db_session, largest_id + 1)  # Non-existent ID

def test_query_language_by_code(db_session : Session, language_session_test : Dict[str, Language]):
    queried_lang = query_language_by_code(db_session, "en")
    assert queried_lang.language_name == "English"
    assert queried_lang.language_code == "en"

    queried_lang = query_language_by_code(db_session, "fr")
    assert queried_lang.language_name == "French"
    assert queried_lang.language_code == "fr"

    with pytest.raises(LanguageNotFoundException):
        query_language_by_code(db_session, "xx")  # Non-existent code

def test_query_all_languages(db_session : Session, language_session_test : Dict[str, Language]):
    queried_languages = query_all_languages(db_session)
    assert len(queried_languages) == len(language_session_test)
    names_and_codes = {(lang.language_name, lang.language_code) for lang in queried_languages}
    expected_names_and_codes = {(lang.language_name, lang.language_code) for _, lang in language_session_test.items()}
    assert len(names_and_codes.symmetric_difference(expected_names_and_codes)) == 0