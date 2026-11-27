import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient

from src.models import ReaderPartner, ReaderPartnerKey
from src.public.router import CHAPTER_CACHE_CONTROL, NOVELS_CACHE_CONTROL, TOC_CACHE_CONTROL


def _seed_novel(
    client: TestClient,
    headers: dict[str, str],
    external_id: str,
    title: str,
    chapters: list[dict[str, object]],
) -> str:
    resp = client.put(
        f"/ingest/novels/{external_id}",
        headers=headers,
        json={"title": title, "description": f"Desc for {title}", "author": "Author", "languageCode": "en"},
    )
    assert resp.status_code == 200
    novel_id: str = resp.json()["novelId"]
    if chapters:
        ch_resp = client.put(
            f"/ingest/novels/{external_id}/chapters",
            headers=headers,
            json={"chapters": chapters},
        )
        assert ch_resp.status_code == 200
    return novel_id


def test_public_reads_and_404s(
    client: TestClient,
    create_partner_with_key: Callable[[str], tuple[ReaderPartner, ReaderPartnerKey, str]],
) -> None:
    _, _, raw_key = create_partner_with_key("Studio")
    headers = {"Authorization": f"Bearer {raw_key}"}

    # Empty catalog
    empty = client.get("/novels")
    assert empty.status_code == 200
    assert empty.json() == []
    assert empty.headers["cache-control"] == NOVELS_CACHE_CONTROL
    assert empty.headers["etag"].startswith('"')

    # 404s for missing novel/chapter
    missing_id = str(uuid.uuid4())
    assert client.get(f"/novels/{missing_id}").status_code == 404
    assert client.get(f"/novels/{missing_id}/chapters").status_code == 404
    assert client.get(f"/novels/{missing_id}/chapters/1").status_code == 404

    novel_id = _seed_novel(
        client,
        headers,
        "ext-1",
        "Starfall",
        [
            {"chapterNum": 1, "title": "Awakening", "body": "Line 1", "externalVersion": "c1"},
            {"chapterNum": 3, "title": "Crossing", "body": "Line 3", "externalVersion": "c3"},
            {"chapterNum": 7, "title": "Finale", "body": "Line 7", "externalVersion": "c7"},
        ],
    )

    novels = client.get("/novels")
    assert novels.status_code == 200
    assert len(novels.json()) == 1
    assert novels.json()[0]["novelId"] == novel_id
    assert novels.json()[0]["title"] == "Starfall"

    detail = client.get(f"/novels/{novel_id}")
    assert detail.status_code == 200
    assert detail.headers["cache-control"] == NOVELS_CACHE_CONTROL
    assert detail.json()["title"] == "Starfall"

    toc = client.get(f"/novels/{novel_id}/chapters")
    assert toc.status_code == 200
    assert toc.headers["cache-control"] == TOC_CACHE_CONTROL
    assert [c["chapterNum"] for c in toc.json()] == [1, 3, 7]

    # Missing chapter number in existing novel
    assert client.get(f"/novels/{novel_id}/chapters/2").status_code == 404

    # Middle chapter includes prev/next across gaps
    ch3 = client.get(f"/novels/{novel_id}/chapters/3")
    assert ch3.status_code == 200
    assert ch3.headers["cache-control"] == CHAPTER_CACHE_CONTROL
    data3 = ch3.json()
    assert data3["novelId"] == novel_id
    assert data3["novelTitle"] == "Starfall"
    assert data3["chapterNum"] == 3
    assert data3["title"] == "Crossing"
    assert data3["body"] == "Line 3"
    assert data3["externalVersion"] == "c3"
    assert data3["prev"] == {"chapterNum": 1, "title": "Awakening"}
    assert data3["next"] == {"chapterNum": 7, "title": "Finale"}

    # First chapter has prev=None, last chapter has next=None
    ch1 = client.get(f"/novels/{novel_id}/chapters/1").json()
    assert ch1["prev"] is None
    assert ch1["next"] == {"chapterNum": 3, "title": "Crossing"}

    ch7 = client.get(f"/novels/{novel_id}/chapters/7").json()
    assert ch7["prev"] == {"chapterNum": 3, "title": "Crossing"}
    assert ch7["next"] is None


def test_etag_304_and_cache_busting(
    client: TestClient,
    create_partner_with_key: Callable[[str], tuple[ReaderPartner, ReaderPartnerKey, str]],
) -> None:
    _, _, raw_key = create_partner_with_key("Studio")
    headers = {"Authorization": f"Bearer {raw_key}"}
    novel_id = _seed_novel(
        client,
        headers,
        "ext-cache",
        "Cached Tale",
        [
            {"chapterNum": 1, "title": "One", "body": "Body one"},
            {"chapterNum": 2, "title": "Two", "body": "Body two"},
        ],
    )

    # /novels ETag + weak/list/wildcard If-None-Match
    novels_res = client.get("/novels")
    novels_etag = novels_res.headers["etag"]
    assert client.get("/novels", headers={"If-None-Match": novels_etag}).status_code == 304
    assert client.get("/novels", headers={"If-None-Match": f"W/{novels_etag}"}).status_code == 304
    assert client.get("/novels", headers={"If-None-Match": f'"other", {novels_etag}'}).status_code == 304
    assert client.get("/novels", headers={"If-None-Match": "*"}).status_code == 304

    # /novels/{novelId} ETag
    novel_res = client.get(f"/novels/{novel_id}")
    novel_etag = novel_res.headers["etag"]
    res_304 = client.get(f"/novels/{novel_id}", headers={"If-None-Match": novel_etag})
    assert res_304.status_code == 304
    assert res_304.headers["etag"] == novel_etag
    assert res_304.headers["cache-control"] == NOVELS_CACHE_CONTROL

    # /novels/{novelId}/chapters TOC ETag
    toc_res = client.get(f"/novels/{novel_id}/chapters")
    toc_etag = toc_res.headers["etag"]
    assert client.get(f"/novels/{novel_id}/chapters", headers={"If-None-Match": toc_etag}).status_code == 304

    # Chapter 1 ETag
    ch1_res = client.get(f"/novels/{novel_id}/chapters/1")
    ch1_etag = ch1_res.headers["etag"]
    ch1_304 = client.get(f"/novels/{novel_id}/chapters/1", headers={"If-None-Match": ch1_etag})
    assert ch1_304.status_code == 304
    assert ch1_304.headers["etag"] == ch1_etag
    assert ch1_304.headers["cache-control"] == CHAPTER_CACHE_CONTROL

    # Updating chapter 1 body busts chapter 1 ETag AND TOC ETag
    client.put(
        "/ingest/novels/ext-cache/chapters",
        headers=headers,
        json={"chapters": [{"chapterNum": 1, "title": "One", "body": "Body one revised"}]},
    )
    ch1_after_body = client.get(f"/novels/{novel_id}/chapters/1", headers={"If-None-Match": ch1_etag})
    assert ch1_after_body.status_code == 200
    assert ch1_after_body.json()["body"] == "Body one revised"
    ch1_etag_v2 = ch1_after_body.headers["etag"]
    assert ch1_etag_v2 != ch1_etag

    toc_after = client.get(f"/novels/{novel_id}/chapters", headers={"If-None-Match": toc_etag})
    assert toc_after.status_code == 200
    assert toc_after.headers["etag"] != toc_etag

    # Adding chapter 3 does NOT bust chapter 1 ETag (next is still chapter 2),
    # but DOES bust chapter 2 ETag (next changed from None to chapter 3)!
    ch2_before = client.get(f"/novels/{novel_id}/chapters/2")
    ch2_etag_v1 = ch2_before.headers["etag"]
    assert ch2_before.json()["next"] is None

    client.put(
        "/ingest/novels/ext-cache/chapters",
        headers=headers,
        json={"chapters": [{"chapterNum": 3, "title": "Three", "body": "Body three"}]},
    )
    assert client.get(f"/novels/{novel_id}/chapters/1", headers={"If-None-Match": ch1_etag_v2}).status_code == 304

    ch2_after = client.get(f"/novels/{novel_id}/chapters/2", headers={"If-None-Match": ch2_etag_v1})
    assert ch2_after.status_code == 200
    assert ch2_after.json()["next"] == {"chapterNum": 3, "title": "Three"}
    assert ch2_after.headers["etag"] != ch2_etag_v1
