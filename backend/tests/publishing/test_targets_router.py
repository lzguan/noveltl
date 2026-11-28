import uuid
from datetime import timedelta

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.utils import create_access_token
from src.config import publishing_settings
from src.main import app
from src.publishing.client import ReaderClient
from src.publishing.dependencies import get_reader_client
from test_support.publishing import FakeReaderServer
from test_support.test_data.scenarios import DatabaseScenario, PasswordHash, ScenarioBuilder


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.user_name}, timedelta(minutes=30))}"}


@pytest.fixture
def target_users(test_db: Session, no_hash: PasswordHash) -> DatabaseScenario:
    builder = ScenarioBuilder(test_db, no_hash)
    builder.user("alice", "pub_alice", "pass1")
    builder.user("bob", "pub_bob", "pass2")
    builder.user("charlie", "pub_charlie", "pass3")
    return builder.finish()


def test_target_test_and_save_crud_and_rotation(
    client: TestClient,
    target_users: DatabaseScenario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(publishing_settings, "ALLOW_PRIVATE_PUBLISH_TARGETS", False)
    fake_reader = FakeReaderServer(
        valid_api_keys={"rapi_initial_key_1234567890abcdef"},
        instance_name="Main Reader",
        public_base_url="https://reader.example.com",
    )
    app.dependency_overrides[get_reader_client] = lambda: ReaderClient(transport=fake_reader.transport())
    alice = target_users.users["alice"]
    bob = target_users.users["bob"]

    # SSRF private target blocked before calling Reader.
    ssrf_resp = client.post(
        "/publishing/targets",
        json={
            "name": "Local Blocked",
            "apiBaseUrl": "http://127.0.0.1:8001",
            "apiKey": "rapi_initial_key_1234567890abcdef",
        },
        headers=_headers(alice),
    )
    assert ssrf_resp.status_code == status.HTTP_400_BAD_REQUEST
    assert fake_reader.requests == []

    # Invalid API key rejected by Reader health check.
    bad_key_resp = client.post(
        "/publishing/targets",
        json={
            "name": "Bad Key",
            "apiBaseUrl": "https://93.184.216.34/",
            "apiKey": "rapi_wrong_key_1234567890abcdef",
        },
        headers=_headers(alice),
    )
    assert bad_key_resp.status_code == status.HTTP_502_BAD_GATEWAY

    # Unsupported protocol version rejected.
    fake_reader.protocol_version = 99
    bad_proto_resp = client.post(
        "/publishing/targets",
        json={
            "name": "Bad Proto",
            "apiBaseUrl": "https://93.184.216.34/",
            "apiKey": "rapi_initial_key_1234567890abcdef",
        },
        headers=_headers(alice),
    )
    assert bad_proto_resp.status_code == status.HTTP_502_BAD_GATEWAY
    fake_reader.protocol_version = 1

    # Valid Test & Save succeeds and never exposes encrypted/raw key.
    created_resp = client.post(
        "/publishing/targets",
        json={
            "name": "Production Reader",
            "apiBaseUrl": "https://93.184.216.34/",
            "apiKey": "rapi_initial_key_1234567890abcdef",
        },
        headers=_headers(alice),
    )
    assert created_resp.status_code == status.HTTP_201_CREATED
    created = created_resp.json()
    assert created["name"] == "Production Reader"
    assert created["apiBaseUrl"] == "https://93.184.216.34"
    assert created["publicBaseUrl"] == "https://reader.example.com"
    assert created["keyPrefix"] == "rapi_initial_key"
    assert created["role"] == "owner"
    assert "encryptedApiKey" not in created
    assert "apiKey" not in created
    target_id = created["targetId"]

    # Owner sees target; non-member does not.
    assert len(client.get("/publishing/targets", headers=_headers(alice)).json()) == 1
    assert client.get("/publishing/targets", headers=_headers(bob)).json() == []

    # Re-test updates publicBaseUrl when Reader reports a new one.
    fake_reader.public_base_url = "https://books.example.com"
    test_resp = client.post(f"/publishing/targets/{target_id}/test", headers=_headers(alice))
    assert test_resp.status_code == status.HTTP_200_OK
    assert test_resp.json()["publicBaseUrl"] == "https://books.example.com"
    assert client.get("/publishing/targets", headers=_headers(alice)).json()[0]["publicBaseUrl"] == (
        "https://books.example.com"
    )

    # Non-member cannot test or patch or delete.
    assert client.post(f"/publishing/targets/{target_id}/test", headers=_headers(bob)).status_code == 403
    assert client.patch(f"/publishing/targets/{target_id}", json={"name": "Hack"}, headers=_headers(bob)).status_code == 403
    assert client.delete(f"/publishing/targets/{target_id}", headers=_headers(bob)).status_code == 403

    # Rotate API key: bad new key fails 502 without changing stored key.
    bad_rotate = client.patch(
        f"/publishing/targets/{target_id}",
        json={"apiKey": "rapi_invalid_rotated_key_123456"},
        headers=_headers(alice),
    )
    assert bad_rotate.status_code == status.HTTP_502_BAD_GATEWAY

    # Rotate API key to valid new key + rename.
    fake_reader.valid_api_keys.add("rapi_rotated_key_9876543210fedcba")
    rotated = client.patch(
        f"/publishing/targets/{target_id}",
        json={"name": "Renamed Reader", "apiKey": "rapi_rotated_key_9876543210fedcba"},
        headers=_headers(alice),
    )
    assert rotated.status_code == status.HTTP_200_OK
    assert rotated.json()["name"] == "Renamed Reader"
    assert rotated.json()["keyPrefix"] == "rapi_rotated_key"

    # Old key can now be revoked on Reader and test still succeeds with rotated key.
    fake_reader.valid_api_keys.remove("rapi_initial_key_1234567890abcdef")
    assert client.post(f"/publishing/targets/{target_id}/test", headers=_headers(alice)).status_code == 200

    # Delete target.
    deleted = client.delete(f"/publishing/targets/{target_id}", headers=_headers(alice))
    assert deleted.status_code == status.HTTP_200_OK
    assert client.get("/publishing/targets", headers=_headers(alice)).json() == []
    assert client.post(f"/publishing/targets/{target_id}/test", headers=_headers(alice)).status_code == 404


def test_target_sharing_and_last_owner_guard(
    client: TestClient,
    target_users: DatabaseScenario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(publishing_settings, "ALLOW_PRIVATE_PUBLISH_TARGETS", True)
    fake_reader = FakeReaderServer()
    app.dependency_overrides[get_reader_client] = lambda: ReaderClient(transport=fake_reader.transport())
    alice = target_users.users["alice"]
    bob = target_users.users["bob"]
    charlie = target_users.users["charlie"]

    target_id = client.post(
        "/publishing/targets",
        json={
            "name": "Shared Reader",
            "apiBaseUrl": "http://reader-api:8001",
            "apiKey": "rapi_test_secret_key_1234567890",
        },
        headers=_headers(alice),
    ).json()["targetId"]

    # Last owner cannot demote or remove themselves.
    demote_self = client.post(
        f"/publishing/targets/{target_id}/members",
        json={"userId": str(alice.user_id), "role": "publisher"},
        headers=_headers(alice),
    )
    assert demote_self.status_code == status.HTTP_400_BAD_REQUEST

    delete_self = client.delete(
        f"/publishing/targets/{target_id}/members/{alice.user_id}",
        headers=_headers(alice),
    )
    assert delete_self.status_code == status.HTTP_400_BAD_REQUEST

    # Add Bob as publisher by username.
    add_bob = client.post(
        f"/publishing/targets/{target_id}/members",
        json={"userName": bob.user_name, "role": "publisher"},
        headers=_headers(alice),
    )
    assert add_bob.status_code == status.HTTP_200_OK
    assert add_bob.json()["userId"] == str(bob.user_id)
    assert add_bob.json()["role"] == "publisher"

    # Bob sees the target and can test it, but cannot manage members, patch, or delete.
    bob_targets = client.get("/publishing/targets", headers=_headers(bob)).json()
    assert len(bob_targets) == 1
    assert bob_targets[0]["role"] == "publisher"
    assert client.post(f"/publishing/targets/{target_id}/test", headers=_headers(bob)).status_code == 200
    assert client.get(f"/publishing/targets/{target_id}/members", headers=_headers(bob)).status_code == 403
    assert (
        client.post(
            f"/publishing/targets/{target_id}/members",
            json={"userName": charlie.user_name, "role": "publisher"},
            headers=_headers(bob),
        ).status_code
        == 403
    )
    assert client.patch(f"/publishing/targets/{target_id}", json={"name": "Nope"}, headers=_headers(bob)).status_code == 403
    assert client.delete(f"/publishing/targets/{target_id}", headers=_headers(bob)).status_code == 403

    # Promote Bob to owner -> now Alice can be demoted or removed.
    promote_bob = client.post(
        f"/publishing/targets/{target_id}/members",
        json={"userId": str(bob.user_id), "role": "owner"},
        headers=_headers(alice),
    )
    assert promote_bob.status_code == status.HTTP_200_OK
    assert promote_bob.json()["role"] == "owner"

    members = client.get(f"/publishing/targets/{target_id}/members", headers=_headers(bob)).json()
    assert {m["userName"]: m["role"] for m in members} == {
        alice.user_name: "owner",
        bob.user_name: "owner",
    }

    demote_alice = client.post(
        f"/publishing/targets/{target_id}/members",
        json={"userName": alice.user_name, "role": "publisher"},
        headers=_headers(bob),
    )
    assert demote_alice.status_code == status.HTTP_200_OK
    assert demote_alice.json()["role"] == "publisher"

    remove_alice = client.delete(
        f"/publishing/targets/{target_id}/members/{alice.user_id}",
        headers=_headers(bob),
    )
    assert remove_alice.status_code == status.HTTP_200_OK
    assert client.get("/publishing/targets", headers=_headers(alice)).json() == []

    # Unknown user returns 404.
    missing_user = client.post(
        f"/publishing/targets/{target_id}/members",
        json={"userId": str(uuid.uuid4()), "role": "publisher"},
        headers=_headers(bob),
    )
    assert missing_user.status_code == status.HTTP_404_NOT_FOUND
