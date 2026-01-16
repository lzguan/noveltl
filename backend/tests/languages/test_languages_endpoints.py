from fastapi.testclient import TestClient

from src.languages.models import Language


def test_languages_endpoints(client : TestClient, sample_languages : dict[str, Language]) -> None:
    # Test GET /languages
    response = client.get("/languages")
    assert response.status_code == 200
    languages = response.json()
    assert isinstance(languages, list)
    assert len(languages) == 4

    lang_codes = {lang['language_code'] for lang in languages}
    assert "en" in lang_codes
    assert "zh" in lang_codes
    assert "kr" in lang_codes
    assert "jp" in lang_codes

    # Test GET /languages/{language_code} for English
    response = client.get("/languages/en")
    assert response.status_code == 200
    lang_en = response.json()
    assert lang_en['language_name'] == "English"
    assert lang_en['language_code'] == "en"

    # Test GET /languages/{language_code} for Chinese
    response = client.get("/languages/zh")
    assert response.status_code == 200
    lang_zh = response.json()
    assert lang_zh['language_name'] == "Chinese"
    assert lang_zh['language_code'] == "zh"

    # Test GET /languages/{language_code} for non-existent code
    response = client.get("/languages/xx")
    assert response.status_code == 404
