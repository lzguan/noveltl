from fastapi.testclient import TestClient

from test_support.test_data.scenarios import DatabaseScenario


def test_languages_endpoints(client: TestClient, sample_scenario: DatabaseScenario) -> None:
    response = client.get("/languages")
    assert response.status_code == 200
    languages = response.json()
    assert isinstance(languages, list)
    assert len(languages) == 4

    lang_codes = {lang["languageCode"] for lang in languages}
    assert "en" in lang_codes
    assert "zh" in lang_codes
    assert "kr" in lang_codes
    assert "jp" in lang_codes

    # Test GET /languages/{language_code} for English
    response = client.get("/languages/en")
    assert response.status_code == 200
    lang_en = response.json()
    assert lang_en["languageName"] == "English"
    assert lang_en["languageCode"] == "en"

    # Test GET /languages/{language_code} for Chinese
    response = client.get("/languages/zh")
    assert response.status_code == 200
    lang_zh = response.json()
    assert lang_zh["languageName"] == "Chinese"
    assert lang_zh["languageCode"] == "zh"

    # Test GET /languages/{language_code} for non-existent code
    response = client.get("/languages/xx")
    assert response.status_code == 404
