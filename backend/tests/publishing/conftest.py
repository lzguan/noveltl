import pytest

from src.config import publishing_settings


@pytest.fixture(autouse=True)
def _configure_publishing_encryption_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        publishing_settings,
        "PUBLISH_KEY_ENCRYPTION_SECRET",
        "test-publish-key-encryption-secret",
    )
