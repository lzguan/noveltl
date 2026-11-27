import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from scripts.manage_partners import create_partner, list_keys, mint_key, revoke_key
from src.models import ReaderPartner, ReaderPartnerKey


def test_missing_invalid_and_malformed_bearer_rejected(client: TestClient) -> None:
    resp_missing = client.get("/ingest/health")
    assert resp_missing.status_code == 401
    assert resp_missing.headers.get("cache-control") == "no-store"

    resp_bad = client.get("/ingest/health", headers={"Authorization": "Bearer not-a-real-key"})
    assert resp_bad.status_code == 401
    assert resp_bad.headers.get("cache-control") == "no-store"

    resp_wrong_scheme = client.get("/ingest/health", headers={"Authorization": "Basic abc123"})
    assert resp_wrong_scheme.status_code == 401


@pytest.mark.asyncio
async def test_zero_downtime_key_rotation_and_revocation(
    client: TestClient,
    async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with async_session_factory() as db:
        partner = await create_partner(db, "Studio Primary")
        key1, raw1 = await mint_key(db, partner.partner_id)
        key2, raw2 = await mint_key(db, partner.partner_id)

        all_keys = await list_keys(db, partner.partner_id)
        assert {k.key_id for k in all_keys} == {key1.key_id, key2.key_id}
        assert all(k.revoked_at is None for k in all_keys)

    # Both keys work simultaneously during rotation.
    assert client.get("/ingest/health", headers={"Authorization": f"Bearer {raw1}"}).status_code == 200
    assert client.get("/ingest/health", headers={"Authorization": f"Bearer {raw2}"}).status_code == 200

    # Revoke old key; new key continues working while old key immediately fails with 401.
    async with async_session_factory() as db:
        revoked = await revoke_key(db, key1.key_id)
        assert revoked.revoked_at is not None

    assert client.get("/ingest/health", headers={"Authorization": f"Bearer {raw1}"}).status_code == 401
    assert client.get("/ingest/health", headers={"Authorization": f"Bearer {raw2}"}).status_code == 200


@pytest.mark.asyncio
async def test_manage_partners_errors_on_unknown_ids(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with async_session_factory() as db:
        with pytest.raises(ValueError, match="Partner not found"):
            await mint_key(db, uuid.uuid4())
        with pytest.raises(ValueError, match="Key not found"):
            await revoke_key(db, uuid.uuid4())


def test_partner_isolation(
    client: TestClient,
    create_partner_with_key: Callable[[str], tuple[ReaderPartner, ReaderPartnerKey, str]],
) -> None:
    _, _, key_a = create_partner_with_key("Partner A")
    _, _, key_b = create_partner_with_key("Partner B")
    headers_a = {"Authorization": f"Bearer {key_a}"}
    headers_b = {"Authorization": f"Bearer {key_b}"}

    # Partner A publishes externalId="novel-1"
    upsert_a = client.put(
        "/ingest/novels/novel-1",
        headers=headers_a,
        json={"title": "Partner A Novel", "author": "Author A"},
    )
    assert upsert_a.status_code == 200
    novel_id_a = upsert_a.json()["novelId"]

    chapters_a = client.put(
        "/ingest/novels/novel-1/chapters",
        headers=headers_a,
        json={"chapters": [{"chapterNum": 1, "title": "Ch 1", "body": "Body A"}]},
    )
    assert chapters_a.status_code == 200

    # Partner B sees exists=False for the same externalId and cannot mutate Partner A's novel.
    status_b = client.get("/ingest/novels/novel-1/status", headers=headers_b)
    assert status_b.status_code == 200
    assert status_b.json() == {"exists": False, "novelId": None, "publicUrl": None, "chapters": []}

    assert (
        client.put(
            "/ingest/novels/novel-1/chapters",
            headers=headers_b,
            json={"chapters": [{"chapterNum": 1, "title": "Hijack", "body": "Nope"}]},
        ).status_code
        == 404
    )
    assert (
        client.request(
            "DELETE",
            "/ingest/novels/novel-1/chapters",
            headers=headers_b,
            json={"chapterNums": [1]},
        ).status_code
        == 404
    )

    # Partner B can create its own novel with the same externalId independently.
    upsert_b = client.put(
        "/ingest/novels/novel-1",
        headers=headers_b,
        json={"title": "Partner B Novel"},
    )
    assert upsert_b.status_code == 200
    novel_id_b = upsert_b.json()["novelId"]
    assert novel_id_b != novel_id_a

    # Partner A's novel and chapter remain untouched.
    pub_a = client.get(f"/novels/{novel_id_a}/chapters/1")
    assert pub_a.status_code == 200
    assert pub_a.json()["body"] == "Body A"
