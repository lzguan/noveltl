import hashlib
from collections.abc import Callable

from fastapi.testclient import TestClient

from src.models import ReaderPartner, ReaderPartnerKey


def test_healthz_and_ingest_health(
    client: TestClient,
    create_partner_with_key: Callable[[str], tuple[ReaderPartner, ReaderPartnerKey, str]],
) -> None:
    healthz = client.get("/healthz")
    assert healthz.status_code == 200
    assert healthz.json() == {"ok": True}

    _, _, raw_key = create_partner_with_key("Studio")
    resp = client.get("/ingest/health", headers={"Authorization": f"Bearer {raw_key}"})
    assert resp.status_code == 200
    assert resp.headers.get("cache-control") == "no-store"
    body = resp.json()
    assert body["ok"] is True
    assert body["protocolVersion"] == 1
    assert body["name"]
    assert body["publicBaseUrl"]


def test_ingest_novel_chapters_status_and_delete(
    client: TestClient,
    create_partner_with_key: Callable[[str], tuple[ReaderPartner, ReaderPartnerKey, str]],
) -> None:
    _, _, raw_key = create_partner_with_key("Studio")
    headers = {"Authorization": f"Bearer {raw_key}"}

    # Status before creation
    status_before = client.get("/ingest/novels/ext-42/status", headers=headers)
    assert status_before.status_code == 200
    assert status_before.headers.get("cache-control") == "no-store"
    assert status_before.json() == {"exists": False, "novelId": None, "publicUrl": None, "chapters": []}

    # Pushing chapters before creating novel returns 404
    missing_novel = client.put(
        "/ingest/novels/ext-42/chapters",
        headers=headers,
        json={"chapters": [{"chapterNum": 1, "title": "Ch 1", "body": "Hello"}]},
    )
    assert missing_novel.status_code == 404
    assert missing_novel.headers.get("cache-control") == "no-store"

    # Upsert novel metadata (create)
    created = client.put(
        "/ingest/novels/ext-42",
        headers=headers,
        json={
            "title": "Immortal Path",
            "description": "A cultivation story",
            "author": "Li Ming",
            "languageCode": "en",
        },
    )
    assert created.status_code == 200
    assert created.headers.get("cache-control") == "no-store"
    novel_id = created.json()["novelId"]
    assert created.json()["publicUrl"].endswith(f"/novel/{novel_id}")

    # Idempotent metadata update preserves novelId
    updated = client.put(
        "/ingest/novels/ext-42",
        headers=headers,
        json={
            "title": "Immortal Path Revised",
            "description": "Updated synopsis",
            "author": "Li Ming",
            "languageCode": "en",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["novelId"] == novel_id

    # Batch upsert chapters (including duplicate chapterNum in same batch -> last write wins)
    body_1 = "Paragraph one.\n\nParagraph two."
    body_2 = "Second chapter body."
    upsert_ch = client.put(
        "/ingest/novels/ext-42/chapters",
        headers=headers,
        json={
            "chapters": [
                {"chapterNum": 2, "title": "Arrival", "body": body_2, "externalVersion": "ver-2"},
                {"chapterNum": 1, "title": "Old", "body": "Old body", "externalVersion": "ver-1-old"},
                {"chapterNum": 1, "title": "Prologue", "body": body_1, "externalVersion": "ver-1"},
            ]
        },
    )
    assert upsert_ch.status_code == 200
    assert upsert_ch.headers.get("cache-control") == "no-store"
    assert upsert_ch.json()["novelId"] == novel_id
    assert upsert_ch.json()["upsertedChapterNums"] == [1, 2]

    # Status returns ordered chapters with computed SHA-256 content hashes and externalVersion
    status_after = client.get("/ingest/novels/ext-42/status", headers=headers)
    assert status_after.status_code == 200
    status_data = status_after.json()
    assert status_data["exists"] is True
    assert status_data["novelId"] == novel_id
    assert status_data["publicUrl"].endswith(f"/novel/{novel_id}")
    assert len(status_data["chapters"]) == 2
    assert status_data["chapters"][0]["chapterNum"] == 1
    assert status_data["chapters"][0]["title"] == "Prologue"
    assert status_data["chapters"][0]["contentHash"] == hashlib.sha256(body_1.encode("utf-8")).hexdigest()
    assert status_data["chapters"][0]["externalVersion"] == "ver-1"
    assert status_data["chapters"][1]["chapterNum"] == 2
    assert status_data["chapters"][1]["contentHash"] == hashlib.sha256(body_2.encode("utf-8")).hexdigest()

    # Empty chapter upsert is a no-op
    empty_upsert = client.put(
        "/ingest/novels/ext-42/chapters",
        headers=headers,
        json={"chapters": []},
    )
    assert empty_upsert.status_code == 200
    assert empty_upsert.json()["upsertedChapterNums"] == []

    # Delete chapter 2 and non-existent chapter 99
    deleted = client.request(
        "DELETE",
        "/ingest/novels/ext-42/chapters",
        headers=headers,
        json={"chapterNums": [2, 99]},
    )
    assert deleted.status_code == 200
    assert deleted.headers.get("cache-control") == "no-store"
    assert deleted.json() == {"deletedChapterNums": [2]}

    status_final = client.get("/ingest/novels/ext-42/status", headers=headers)
    assert [c["chapterNum"] for c in status_final.json()["chapters"]] == [1]
