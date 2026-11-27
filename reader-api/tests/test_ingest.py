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


def test_ingest_unified_sync_lifecycle(
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

    # Chapter-only sync before creating novel returns 404
    missing_novel = client.post(
        "/ingest/novels/ext-42/sync",
        headers=headers,
        json={"upserts": [{"chapterNum": 1, "title": "Ch 1", "body": "Hello"}]},
    )
    assert missing_novel.status_code == 404
    assert missing_novel.headers.get("cache-control") == "no-store"

    # Empty sync before creating novel also returns 404
    empty_missing = client.post("/ingest/novels/ext-42/sync", headers=headers, json={})
    assert empty_missing.status_code == 404

    # Create novel + initial chapters in a single atomic sync call (duplicate chapterNum -> last wins)
    body_1 = "Paragraph one.\n\nParagraph two."
    body_2 = "Second chapter body."
    created = client.post(
        "/ingest/novels/ext-42/sync",
        headers=headers,
        json={
            "novel": {
                "title": "Immortal Path",
                "description": "A cultivation story",
                "author": "Li Ming",
                "languageCode": "en",
            },
            "upserts": [
                {"chapterNum": 2, "title": "Arrival", "body": body_2, "externalVersion": "ver-2"},
                {"chapterNum": 1, "title": "Old", "body": "Old body", "externalVersion": "ver-1-old"},
                {"chapterNum": 1, "title": "Prologue", "body": body_1, "externalVersion": "ver-1"},
            ],
        },
    )
    assert created.status_code == 200
    assert created.headers.get("cache-control") == "no-store"
    created_data = created.json()
    novel_id = created_data["novelId"]
    assert created_data["publicUrl"].endswith(f"/novel/{novel_id}")
    assert created_data["upsertedChapterNums"] == [1, 2]

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

    # Subsequent chapter-only sync without `novel` updates existing novel
    body_3 = "Third chapter body."
    chapter_only = client.post(
        "/ingest/novels/ext-42/sync",
        headers=headers,
        json={
            "upserts": [
                {"chapterNum": 3, "title": "Ascent", "body": body_3, "externalVersion": "ver-3"},
            ]
        },
    )
    assert chapter_only.status_code == 200
    assert chapter_only.headers.get("cache-control") == "no-store"
    assert chapter_only.json()["novelId"] == novel_id
    assert chapter_only.json()["upsertedChapterNums"] == [3]

    # Metadata-only sync without `upserts` preserves novelId and chapters
    metadata_only = client.post(
        "/ingest/novels/ext-42/sync",
        headers=headers,
        json={
            "novel": {
                "title": "Immortal Path Revised",
                "description": "Updated synopsis",
                "author": "Li Ming",
                "languageCode": "en",
            }
        },
    )
    assert metadata_only.status_code == 200
    assert metadata_only.json()["novelId"] == novel_id
    assert metadata_only.json()["upsertedChapterNums"] == []

    # Empty sync on existing novel is a no-op
    noop = client.post("/ingest/novels/ext-42/sync", headers=headers, json={})
    assert noop.status_code == 200
    assert noop.json()["novelId"] == novel_id
    assert noop.json()["upsertedChapterNums"] == []

    # Verify public view reflects updated metadata and all 3 chapters
    pub_novel = client.get(f"/novels/{novel_id}")
    assert pub_novel.status_code == 200
    assert pub_novel.json()["title"] == "Immortal Path Revised"
    assert pub_novel.json()["description"] == "Updated synopsis"

    status_final = client.get("/ingest/novels/ext-42/status", headers=headers)
    assert [c["chapterNum"] for c in status_final.json()["chapters"]] == [1, 2, 3]


def test_ingest_partner_isolation_and_legacy_endpoints_removed(
    client: TestClient,
    create_partner_with_key: Callable[[str], tuple[ReaderPartner, ReaderPartnerKey, str]],
) -> None:
    _, _, key_a = create_partner_with_key("Partner A")
    _, _, key_b = create_partner_with_key("Partner B")
    headers_a = {"Authorization": f"Bearer {key_a}"}
    headers_b = {"Authorization": f"Bearer {key_b}"}

    sync_a = client.post(
        "/ingest/novels/shared-ext/sync",
        headers=headers_a,
        json={
            "novel": {"title": "Partner A Title"},
            "upserts": [{"chapterNum": 1, "title": "Ch 1", "body": "Body A"}],
        },
    )
    assert sync_a.status_code == 200
    novel_id_a = sync_a.json()["novelId"]

    # Partner B cannot upsert chapters into Partner A's novel without creating its own
    blocked = client.post(
        "/ingest/novels/shared-ext/sync",
        headers=headers_b,
        json={"upserts": [{"chapterNum": 1, "title": "Hijack", "body": "Nope"}]},
    )
    assert blocked.status_code == 404

    # Partner B syncing with novel metadata creates a separate novel
    sync_b = client.post(
        "/ingest/novels/shared-ext/sync",
        headers=headers_b,
        json={"novel": {"title": "Partner B Title"}},
    )
    assert sync_b.status_code == 200
    assert sync_b.json()["novelId"] != novel_id_a

    # Legacy PUT/DELETE endpoints are removed
    assert client.put("/ingest/novels/shared-ext", headers=headers_a, json={"title": "Old"}).status_code in {404, 405}
    assert (
        client.put("/ingest/novels/shared-ext/chapters", headers=headers_a, json={"chapters": []}).status_code
        in {404, 405}
    )
    assert (
        client.request("DELETE", "/ingest/novels/shared-ext/chapters", headers=headers_a, json={"chapterNums": [1]}).status_code
        in {404, 405}
    )
