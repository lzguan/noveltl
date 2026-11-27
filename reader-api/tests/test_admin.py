import uuid

import pytest
from fastapi.testclient import TestClient

from scripts.manage_partners import main as manage_partners_main
from src.admin.auth import (
    create_admin_token,
    hash_admin_password,
    verify_admin_password,
    verify_admin_token,
)
from src.config import reader_settings

ADMIN_USERNAME = "operator"
ADMIN_PASSWORD = "correct-horse-battery-staple"
ADMIN_SECRET = "test-admin-hmac-secret-0123456789"


@pytest.fixture
def configured_admin(monkeypatch: pytest.MonkeyPatch) -> str:
    password_hash = hash_admin_password(ADMIN_PASSWORD)
    monkeypatch.setattr(reader_settings, "READER_ADMIN_USERNAME", ADMIN_USERNAME)
    monkeypatch.setattr(reader_settings, "READER_ADMIN_PASSWORD_HASH", password_hash)
    monkeypatch.setattr(reader_settings, "READER_ADMIN_SECRET", ADMIN_SECRET)
    monkeypatch.setattr(reader_settings, "READER_ADMIN_TOKEN_TTL_SECONDS", 3600)
    return password_hash


def _login_headers(client: TestClient) -> dict[str, str]:
    resp = client.post(
        "/admin/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    assert resp.status_code == 200
    assert resp.headers.get("cache-control") == "no-store"
    body = resp.json()
    assert body["accessToken"]
    assert body["expiresAt"]
    return {"Authorization": f"Bearer {body['accessToken']}"}


def test_password_hashing_and_cli_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    stored = hash_admin_password("secret-pw")
    assert stored.startswith("scrypt$")
    assert verify_admin_password("secret-pw", stored) is True
    assert verify_admin_password("wrong-pw", stored) is False
    assert verify_admin_password("secret-pw", "invalid-format") is False
    assert verify_admin_password("secret-pw", "scrypt$not-base64!$also-bad!") is False

    exit_code = manage_partners_main(["hash-admin-password", "--password", "cli-secret"])
    assert exit_code == 0
    captured = capsys.readouterr().out.strip()
    assert verify_admin_password("cli-secret", captured) is True


def test_admin_token_verification_and_expiry(
    monkeypatch: pytest.MonkeyPatch,
    configured_admin: str,
) -> None:
    _ = configured_admin
    token, _ = create_admin_token(ADMIN_USERNAME)
    assert verify_admin_token(token) == ADMIN_USERNAME
    assert verify_admin_token(f"{token}tampered") is None
    assert verify_admin_token("malformed") is None

    # Different secret invalidates token
    monkeypatch.setattr(reader_settings, "READER_ADMIN_SECRET", "different-secret")
    assert verify_admin_token(token) is None

    # Expired token rejected
    monkeypatch.setattr(reader_settings, "READER_ADMIN_SECRET", ADMIN_SECRET)
    monkeypatch.setattr(reader_settings, "READER_ADMIN_TOKEN_TTL_SECONDS", -10)
    expired_token, _ = create_admin_token(ADMIN_USERNAME)
    assert verify_admin_token(expired_token) is None


def test_admin_unconfigured_returns_503(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(reader_settings, "READER_ADMIN_USERNAME", "")
    monkeypatch.setattr(reader_settings, "READER_ADMIN_PASSWORD_HASH", "")
    monkeypatch.setattr(reader_settings, "READER_ADMIN_SECRET", "")

    login_resp = client.post("/admin/login", json={"username": "admin", "password": "pw"})
    assert login_resp.status_code == 503
    assert login_resp.headers.get("cache-control") == "no-store"

    partners_resp = client.get("/admin/partners")
    assert partners_resp.status_code == 503
    assert partners_resp.headers.get("cache-control") == "no-store"


def test_admin_auth_rejects_bad_credentials_and_tokens(
    client: TestClient,
    configured_admin: str,
) -> None:
    _ = configured_admin

    bad_pw = client.post("/admin/login", json={"username": ADMIN_USERNAME, "password": "wrong"})
    assert bad_pw.status_code == 401
    assert bad_pw.headers.get("cache-control") == "no-store"

    bad_user = client.post("/admin/login", json={"username": "other", "password": ADMIN_PASSWORD})
    assert bad_user.status_code == 401

    no_auth = client.get("/admin/partners")
    assert no_auth.status_code == 401
    assert no_auth.headers.get("cache-control") == "no-store"

    bad_token = client.get("/admin/partners", headers={"Authorization": "Bearer invalid.token"})
    assert bad_token.status_code == 401
    assert bad_token.headers.get("cache-control") == "no-store"


def test_admin_partner_key_and_novel_management(
    client: TestClient,
    configured_admin: str,
) -> None:
    _ = configured_admin
    admin_headers = _login_headers(client)

    # Create partner
    created_partner = client.post("/admin/partners", headers=admin_headers, json={"name": "Studio Alpha"})
    assert created_partner.status_code == 201
    assert created_partner.headers.get("cache-control") == "no-store"
    partner_id = created_partner.json()["partnerId"]
    assert created_partner.json()["name"] == "Studio Alpha"

    # Mint key for partner
    minted = client.post(f"/admin/partners/{partner_id}/keys", headers=admin_headers)
    assert minted.status_code == 201
    assert minted.headers.get("cache-control") == "no-store"
    key_id = minted.json()["keyId"]
    raw_api_key = minted.json()["apiKey"]
    key_prefix = minted.json()["keyPrefix"]
    assert raw_api_key.startswith(key_prefix)

    # Minted key works for ingest and publishes a novel with 2 chapters
    partner_headers = {"Authorization": f"Bearer {raw_api_key}"}
    assert client.get("/ingest/health", headers=partner_headers).status_code == 200

    synced = client.post(
        "/ingest/novels/admin-ext-1/sync",
        headers=partner_headers,
        json={
            "novel": {
                "title": "Managed Novel",
                "author": "Author X",
                "languageCode": "en",
            },
            "upserts": [
                {"chapterNum": 1, "title": "First", "body": "Body 1"},
                {"chapterNum": 2, "title": "Second", "body": "Body 2"},
            ],
        },
    )
    assert synced.status_code == 200
    novel_id = synced.json()["novelId"]

    # List partners includes key summary (without raw apiKey) and novelCount=1
    partners_list = client.get("/admin/partners", headers=admin_headers)
    assert partners_list.status_code == 200
    assert partners_list.headers.get("cache-control") == "no-store"
    partners = partners_list.json()
    assert len(partners) == 1
    assert partners[0]["partnerId"] == partner_id
    assert partners[0]["novelCount"] == 1
    assert len(partners[0]["keys"]) == 1
    assert partners[0]["keys"][0]["keyId"] == key_id
    assert partners[0]["keys"][0]["keyPrefix"] == key_prefix
    assert partners[0]["keys"][0]["revokedAt"] is None
    assert "apiKey" not in partners[0]["keys"][0]

    # Revoke key: ingest immediately returns 401 and partner list shows revokedAt
    revoke_resp = client.delete(f"/admin/keys/{key_id}", headers=admin_headers)
    assert revoke_resp.status_code == 204
    assert revoke_resp.headers.get("cache-control") == "no-store"
    assert client.get("/ingest/health", headers=partner_headers).status_code == 401

    partners_after_revoke = client.get("/admin/partners", headers=admin_headers).json()
    assert partners_after_revoke[0]["keys"][0]["revokedAt"] is not None

    # List novels shows novel metadata, partnerName, chapterCount, and publicUrl
    novels_resp = client.get("/admin/novels", headers=admin_headers)
    assert novels_resp.status_code == 200
    assert novels_resp.headers.get("cache-control") == "no-store"
    novels = novels_resp.json()
    assert len(novels) == 1
    assert novels[0]["novelId"] == novel_id
    assert novels[0]["title"] == "Managed Novel"
    assert novels[0]["author"] == "Author X"
    assert novels[0]["partnerId"] == partner_id
    assert novels[0]["partnerName"] == "Studio Alpha"
    assert novels[0]["chapterCount"] == 2
    assert novels[0]["publicUrl"].endswith(f"/novel/{novel_id}")

    # Delete a single chapter and verify TOC ETag is busted
    toc_before = client.get(f"/novels/{novel_id}/chapters")
    assert toc_before.status_code == 200
    toc_etag_before = toc_before.headers["etag"]

    del_ch = client.delete(f"/admin/novels/{novel_id}/chapters/2", headers=admin_headers)
    assert del_ch.status_code == 204
    assert del_ch.headers.get("cache-control") == "no-store"

    toc_after = client.get(f"/novels/{novel_id}/chapters", headers={"If-None-Match": toc_etag_before})
    assert toc_after.status_code == 200
    assert toc_after.headers["etag"] != toc_etag_before
    assert [c["chapterNum"] for c in toc_after.json()] == [1]

    # Deleting missing chapter returns 404
    assert client.delete(f"/admin/novels/{novel_id}/chapters/2", headers=admin_headers).status_code == 404

    # Delete novel cascades chapters
    del_novel = client.delete(f"/admin/novels/{novel_id}", headers=admin_headers)
    assert del_novel.status_code == 204
    assert client.get(f"/novels/{novel_id}").status_code == 404
    assert client.get(f"/novels/{novel_id}/chapters/1").status_code == 404
    assert client.get("/admin/novels", headers=admin_headers).json() == []

    # 404s for unknown UUIDs
    missing_id = str(uuid.uuid4())
    assert client.post(f"/admin/partners/{missing_id}/keys", headers=admin_headers).status_code == 404
    assert client.delete(f"/admin/keys/{missing_id}", headers=admin_headers).status_code == 404
    assert client.delete(f"/admin/novels/{missing_id}", headers=admin_headers).status_code == 404
