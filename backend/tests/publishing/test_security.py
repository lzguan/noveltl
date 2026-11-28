import socket

import pytest

from src.config import auth_settings, publishing_settings
from src.publishing.exceptions import (
    InvalidTargetUrlException,
    KeyDecryptionException,
    PublishingNotConfiguredException,
)
from src.publishing.security import (
    decrypt_api_key,
    encrypt_api_key,
    extract_key_prefix,
    validate_target_url,
)


def test_fernet_roundtrip_with_dedicated_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(publishing_settings, "PUBLISH_KEY_ENCRYPTION_SECRET", "dedicated-publish-secret")
    raw_key = "rapi_abcdef1234567890_secret_token"

    encrypted = encrypt_api_key(raw_key)
    assert encrypted != raw_key
    assert raw_key not in encrypted
    assert decrypt_api_key(encrypted) == raw_key


def test_fernet_requires_dedicated_secret_and_rejects_wrong_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_settings, "SECRET_KEY", "auth-secret-should-not-be-used")
    monkeypatch.setattr(publishing_settings, "PUBLISH_KEY_ENCRYPTION_SECRET", "")
    with pytest.raises(PublishingNotConfiguredException):
        encrypt_api_key("rapi_my_secret_key_value")

    monkeypatch.setattr(publishing_settings, "PUBLISH_KEY_ENCRYPTION_SECRET", "publish-secret-one")
    encrypted = encrypt_api_key("rapi_my_secret_key_value")
    assert decrypt_api_key(encrypted) == "rapi_my_secret_key_value"

    monkeypatch.setattr(publishing_settings, "PUBLISH_KEY_ENCRYPTION_SECRET", "publish-secret-two")
    with pytest.raises(KeyDecryptionException):
        decrypt_api_key(encrypted)


def test_extract_key_prefix_never_leaks_full_key() -> None:
    long_key = "rapi_1234567890abcdefghijklmno"
    assert extract_key_prefix(long_key) == long_key[:16]
    assert extract_key_prefix("secret123456") == "secret12"
    assert extract_key_prefix("abcd") == "ab"


@pytest.mark.parametrize(
    "bad_url",
    [
        "",
        "   ",
        "ftp://93.184.216.34",
        "file:///etc/passwd",
        "https://user:pass@93.184.216.34",
        "https://93.184.216.34?foo=bar",
        "https://93.184.216.34#frag",
        "http://127.0.0.1:8001",
        "http://10.0.0.1",
        "http://172.16.0.5",
        "http://192.168.1.10",
        "http://169.254.169.254",
        "http://0.0.0.0",
        "http://[::1]:8001",
        "http://[fe80::1]",
        "http://[::ffff:127.0.0.1]",
    ],
)
async def test_ssrf_guard_blocks_invalid_and_private_urls(
    monkeypatch: pytest.MonkeyPatch, bad_url: str
) -> None:
    monkeypatch.setattr(publishing_settings, "ALLOW_PRIVATE_PUBLISH_TARGETS", False)
    with pytest.raises(InvalidTargetUrlException):
        await validate_target_url(bad_url)


async def test_ssrf_guard_resolves_dns_and_blocks_private_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(publishing_settings, "ALLOW_PRIVATE_PUBLISH_TARGETS", False)

    def fake_private_dns(host: str, port: int, type: int = 0):
        del host, port, type
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.20.30.40", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_private_dns)
    with pytest.raises(InvalidTargetUrlException):
        await validate_target_url("https://internal.example.com/")


async def test_ssrf_guard_allows_public_ip_and_public_dns_and_strips_slash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(publishing_settings, "ALLOW_PRIVATE_PUBLISH_TARGETS", False)

    assert await validate_target_url("https://93.184.216.34/reader///") == "https://93.184.216.34/reader"

    def fake_public_dns(host: str, port: int, type: int = 0):
        del host, port, type
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_public_dns)
    assert await validate_target_url("HTTPS://reader.example.com/") == "https://reader.example.com"


async def test_ssrf_guard_allows_private_targets_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(publishing_settings, "ALLOW_PRIVATE_PUBLISH_TARGETS", True)
    assert await validate_target_url("http://127.0.0.1:8001/") == "http://127.0.0.1:8001"
    assert await validate_target_url("http://reader-api:8001/") == "http://reader-api:8001"
