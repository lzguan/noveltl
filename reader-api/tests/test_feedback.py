import json
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from src.admin.auth import hash_admin_password
from src.config import reader_settings
from src.models import ReaderPartner, ReaderPartnerKey

ADMIN_USERNAME = "feedback-admin"
ADMIN_PASSWORD = "feedback-secret-password"
ADMIN_SECRET = "feedback-admin-hmac-secret-1234567890"


@pytest.fixture
def configured_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    password_hash = hash_admin_password(ADMIN_PASSWORD)
    monkeypatch.setattr(reader_settings, "READER_ADMIN_USERNAME", ADMIN_USERNAME)
    monkeypatch.setattr(reader_settings, "READER_ADMIN_PASSWORD_HASH", password_hash)
    monkeypatch.setattr(reader_settings, "READER_ADMIN_SECRET", ADMIN_SECRET)
    monkeypatch.setattr(reader_settings, "READER_ADMIN_TOKEN_TTL_SECONDS", 3600)
    monkeypatch.setattr(reader_settings, "READER_FEEDBACK_HASH_SALT", "test-feedback-salt")


def _admin_headers(client: TestClient) -> dict[str, str]:
    resp = client.post("/admin/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['accessToken']}"}


def _seed_novel(
    client: TestClient,
    partner_key: str,
    external_id: str,
    title: str,
    chapters: list[dict[str, object]],
) -> str:
    resp = client.post(
        f"/ingest/novels/{external_id}/sync",
        headers={"Authorization": f"Bearer {partner_key}"},
        json={
            "novel": {"title": title, "languageCode": "en"},
            "upserts": chapters,
        },
    )
    assert resp.status_code == 200
    return str(resp.json()["novelId"])


def test_submit_feedback_kinds_and_validation(
    client: TestClient,
    create_partner_with_key: Callable[[str], tuple[ReaderPartner, ReaderPartnerKey, str]],
    configured_admin: None,
) -> None:
    _ = configured_admin
    _, _, raw_key = create_partner_with_key("Feedback Studio")
    novel_id = _seed_novel(
        client,
        raw_key,
        "fb-ext-1",
        "Moonlit Blade",
        [{"chapterNum": 1, "title": "Prologue", "body": "The moon rose over the valley.", "externalVersion": "v1"}],
    )

    chapter_resp = client.get(f"/novels/{novel_id}/chapters/1")
    assert chapter_resp.status_code == 200
    chapter_data = chapter_resp.json()
    assert chapter_data["contentHash"]

    # 1. Reaction (omits contentHash -> falls back to chapter content_hash)
    reaction_resp = client.post(
        f"/novels/{novel_id}/chapters/1/feedback",
        json={"kind": "reaction", "emoji": "love"},
        headers={"User-Agent": "TestReader/1.0", "X-Forwarded-For": "203.0.113.10, 10.0.0.1"},
    )
    assert reaction_resp.status_code == 201
    assert reaction_resp.headers.get("cache-control") == "no-store"
    reaction_body = reaction_resp.json()
    assert reaction_body["feedbackId"]
    assert reaction_body["createdAt"]

    # 2. Issue with anchor and explicit contentHash
    issue_resp = client.post(
        f"/novels/{novel_id}/chapters/1/feedback",
        json={
            "kind": "issue",
            "category": "typo",
            "message": "  Should be valley's edge  ",
            "contentHash": "custom-viewed-hash",
            "anchor": {
                "paragraphIndex": 0,
                "startOffset": 23,
                "endOffset": 29,
                "quote": " valley ",
            },
        },
        headers={"User-Agent": "TestReader/1.0", "X-Forwarded-For": "203.0.113.10"},
    )
    assert issue_resp.status_code == 201
    assert issue_resp.headers.get("cache-control") == "no-store"

    # 3. Comment without anchor
    comment_resp = client.post(
        f"/novels/{novel_id}/chapters/1/feedback",
        json={"kind": "comment", "message": "Great opening chapter!"},
        headers={"User-Agent": "OtherReader/2.0", "X-Forwarded-For": "198.51.100.5"},
    )
    assert comment_resp.status_code == 201

    # Validation failures
    assert (
        client.post(
            f"/novels/{novel_id}/chapters/1/feedback",
            json={"kind": "reaction", "emoji": "not_an_emoji"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/novels/{novel_id}/chapters/1/feedback",
            json={"kind": "issue", "category": "typo", "message": "   "},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/novels/{novel_id}/chapters/1/feedback",
            json={"kind": "comment", "message": "   "},
        ).status_code
        == 422
    )
    # Invalid anchor: endOffset <= startOffset
    assert (
        client.post(
            f"/novels/{novel_id}/chapters/1/feedback",
            json={
                "kind": "issue",
                "category": "formatting",
                "message": "Broken span",
                "anchor": {"paragraphIndex": 0, "startOffset": 10, "endOffset": 10, "quote": "word"},
            },
        ).status_code
        == 422
    )
    # Invalid anchor: blank quote after strip
    assert (
        client.post(
            f"/novels/{novel_id}/chapters/1/feedback",
            json={
                "kind": "comment",
                "message": "Blank quote",
                "anchor": {"paragraphIndex": 0, "startOffset": 0, "endOffset": 3, "quote": "   "},
            },
        ).status_code
        == 422
    )
    # Invalid anchor: negative paragraph index
    assert (
        client.post(
            f"/novels/{novel_id}/chapters/1/feedback",
            json={
                "kind": "comment",
                "message": "Bad paragraph",
                "anchor": {"paragraphIndex": -1, "startOffset": 0, "endOffset": 3, "quote": "The"},
            },
        ).status_code
        == 422
    )

    # 404 for unknown chapter or unknown novel
    assert (
        client.post(
            f"/novels/{novel_id}/chapters/99/feedback",
            json={"kind": "reaction", "emoji": "funny"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/novels/{uuid.uuid4()}/chapters/1/feedback",
            json={"kind": "reaction", "emoji": "funny"},
        ).status_code
        == 404
    )

    # Verify stored items via admin list
    admin_headers = _admin_headers(client)
    listed = client.get("/admin/feedback", headers=admin_headers)
    assert listed.status_code == 200
    assert listed.headers.get("cache-control") == "no-store"
    items = listed.json()["items"]
    assert len(items) == 3

    by_kind = {item["kind"]: item for item in items}
    assert by_kind["reaction"]["contentHash"] == chapter_data["contentHash"]
    assert by_kind["reaction"]["externalVersion"] == "v1"
    assert by_kind["reaction"]["payload"] == {"emoji": "love"}
    assert by_kind["reaction"]["novelTitle"] == "Moonlit Blade"

    assert by_kind["issue"]["contentHash"] == "custom-viewed-hash"
    assert by_kind["issue"]["payload"] == {
        "category": "typo",
        "message": "Should be valley's edge",
        "anchor": {
            "paragraphIndex": 0,
            "startOffset": 23,
            "endOffset": 29,
            "quote": "valley",
        },
    }
    # Same IP+UA -> same clientHash; different IP+UA -> different clientHash; never raw IP/UA
    assert by_kind["reaction"]["clientHash"] == by_kind["issue"]["clientHash"]
    assert by_kind["comment"]["clientHash"] != by_kind["reaction"]["clientHash"]
    assert "203.0.113.10" not in by_kind["reaction"]["clientHash"]
    assert "TestReader" not in by_kind["reaction"]["clientHash"]


def test_admin_feedback_list_filtering_pagination_and_export(
    client: TestClient,
    create_partner_with_key: Callable[[str], tuple[ReaderPartner, ReaderPartnerKey, str]],
    configured_admin: None,
) -> None:
    _ = configured_admin
    _, _, raw_key = create_partner_with_key("Export Studio")
    novel_a = _seed_novel(
        client,
        raw_key,
        "fb-a",
        "Novel A",
        [{"chapterNum": 1, "title": "Ch 1", "body": "Alpha body", "externalVersion": "a1"}],
    )
    novel_b = _seed_novel(
        client,
        raw_key,
        "fb-b",
        "Novel B",
        [{"chapterNum": 1, "title": "Ch 1", "body": "Beta body"}],
    )

    # Auth enforcement on admin feedback endpoints
    assert client.get("/admin/feedback").status_code == 401
    assert client.get("/admin/feedback/export").status_code == 401

    admin_headers = _admin_headers(client)

    fb1 = client.post(
        f"/novels/{novel_a}/chapters/1/feedback",
        json={"kind": "reaction", "emoji": "funny"},
    ).json()
    fb2 = client.post(
        f"/novels/{novel_a}/chapters/1/feedback",
        json={"kind": "issue", "category": "mistranslation", "message": "Wrong idiom"},
    ).json()
    fb3 = client.post(
        f"/novels/{novel_b}/chapters/1/feedback",
        json={"kind": "comment", "message": "Loved this scene"},
    ).json()

    # Filter by novelId and kind
    only_a = client.get(f"/admin/feedback?novelId={novel_a}", headers=admin_headers).json()
    assert len(only_a["items"]) == 2
    assert all(item["novelId"] == novel_a for item in only_a["items"])

    only_issues = client.get("/admin/feedback?kind=issue", headers=admin_headers).json()
    assert len(only_issues["items"]) == 1
    assert only_issues["items"][0]["feedbackId"] == fb2["feedbackId"]

    # Cursor pagination (DESC order)
    page1 = client.get("/admin/feedback?limit=2", headers=admin_headers).json()
    assert len(page1["items"]) == 2
    assert page1["nextCursor"] is not None

    page2 = client.get(f"/admin/feedback?limit=2&before={page1['nextCursor']}", headers=admin_headers).json()
    assert len(page2["items"]) == 1
    assert page2["nextCursor"] is None

    seen_ids = [item["feedbackId"] for item in page1["items"] + page2["items"]]
    assert seen_ids == [fb3["feedbackId"], fb2["feedbackId"], fb1["feedbackId"]]

    # Invalid cursor rejected with 422
    assert client.get("/admin/feedback?before=not-valid-cursor", headers=admin_headers).status_code == 422

    # Full NDJSON export (ASC order)
    export_all = client.get("/admin/feedback/export", headers=admin_headers)
    assert export_all.status_code == 200
    assert export_all.headers.get("cache-control") == "no-store"
    assert export_all.headers["content-type"].startswith("application/x-ndjson")
    export_until = export_all.headers["x-export-until"]
    assert export_until

    lines = [json.loads(line) for line in export_all.text.strip().splitlines()]
    assert [row["feedbackId"] for row in lines] == [fb1["feedbackId"], fb2["feedbackId"], fb3["feedbackId"]]
    assert set(lines[0].keys()) == {
        "feedbackId",
        "novelId",
        "chapterId",
        "chapterNum",
        "contentHash",
        "externalVersion",
        "kind",
        "payload",
        "clientHash",
        "createdAt",
    }
    assert lines[0]["externalVersion"] == "a1"
    assert lines[2]["externalVersion"] is None

    # Incremental pull using since=X-Export-Until yields 0 rows (exclusive >)
    export_empty = client.get(
        "/admin/feedback/export",
        params={"since": export_until},
        headers=admin_headers,
    )
    assert export_empty.status_code == 200
    assert export_empty.text == ""

    # Insert one more row after export_until, then pull with since=export_until -> gets only the new row
    fb4 = client.post(
        f"/novels/{novel_b}/chapters/1/feedback",
        json={"kind": "reaction", "emoji": "shocked"},
    ).json()

    export_inc = client.get(
        "/admin/feedback/export",
        params={"since": export_until},
        headers=admin_headers,
    )
    assert export_inc.status_code == 200
    inc_lines = [json.loads(line) for line in export_inc.text.strip().splitlines()]
    assert [row["feedbackId"] for row in inc_lines] == [fb4["feedbackId"]]

    # Explicit until bound in the past excludes all rows
    past_until = (datetime.fromisoformat(fb1["createdAt"]) - timedelta(seconds=10)).isoformat()
    export_past = client.get(
        "/admin/feedback/export",
        params={"until": past_until},
        headers=admin_headers,
    )
    assert export_past.status_code == 200
    assert export_past.text == ""
