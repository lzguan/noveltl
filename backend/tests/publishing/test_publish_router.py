import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from src.auth.constants import UserType
from src.auth.models import User
from src.auth.utils import create_access_token
from src.config import publishing_settings
from src.main import app
from src.novels.constants import Role, Visibility
from src.publishing.client import ReaderClient
from src.publishing.dependencies import get_reader_client
from src.publishing.exceptions import PublishEnqueueFailedException
from src.publishing.models import PublishJob
from test_support.publishing import FakeReaderServer, RecordingPublishDispatcher
from test_support.test_data.scenarios import DatabaseScenario, PasswordHash, ScenarioBuilder


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.user_name}, timedelta(minutes=30))}"}


@pytest.fixture
def publish_scenario(test_db: Session, no_hash: PasswordHash) -> DatabaseScenario:
    builder = ScenarioBuilder(test_db, no_hash)
    builder.language("en", "English", "en")
    builder.user("owner", "p_owner", "pass1")
    builder.user("editor", "p_editor", "pass2")
    builder.user("viewer", "p_viewer", "pass3")
    builder.user("outsider", "p_outsider", "pass4")
    builder.user("admin", "p_admin", "pass5", UserType.ADMIN)
    builder.source_work("sw", "Publish Source Work")
    builder.novel(
        "novel",
        title="Unpublished Chronicles",
        language="en",
        source_work="sw",
        visibility=Visibility.PRIVATE,
        description="A test novel",
        author="Author Name",
    )
    builder.contributor("owner", novel="novel", user="owner", role=Role.OWNER)
    builder.contributor("editor", novel="novel", user="editor", role=Role.EDITOR)
    builder.contributor("viewer", novel="novel", user="viewer", role=Role.VIEWER)

    # Mix public and non-public chapters (publishing must be decoupled from chapter_is_public).
    builder.chapter("ch1", novel="novel", number=1, title="Ch 1", is_public=False)
    builder.content("ch1_v1", chapter="ch1", version=1, text="Chapter 1 v1")
    builder.content("ch1_v2", chapter="ch1", version=2, text="Chapter 1 v2")

    builder.chapter("ch2", novel="novel", number=2, title="Ch 2", is_public=False)
    builder.content("ch2_v1", chapter="ch2", version=1, text="Chapter 2 v1")

    builder.chapter("ch3", novel="novel", number=3, title="Ch 3", is_public=True)
    builder.content("ch3_v1", chapter="ch3", version=1, text="Chapter 3 v1")

    return builder.finish()


def _create_target(client: TestClient, owner: User, *, name: str = "Reader Target") -> str:
    resp = client.post(
        "/publishing/targets",
        json={
            "name": name,
            "apiBaseUrl": "http://reader-api:8001",
            "apiKey": "rapi_test_secret_key_1234567890",
        },
        headers=_headers(owner),
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()["targetId"]


def test_publish_status_live_diff_and_permissions(
    client: TestClient,
    publish_scenario: DatabaseScenario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(publishing_settings, "ALLOW_PRIVATE_PUBLISH_TARGETS", True)
    fake_reader = FakeReaderServer()
    app.dependency_overrides[get_reader_client] = lambda: ReaderClient(transport=fake_reader.transport())

    owner = publish_scenario.users["owner"]
    editor = publish_scenario.users["editor"]
    viewer = publish_scenario.users["viewer"]
    outsider = publish_scenario.users["outsider"]
    novel = publish_scenario.novels["novel"]
    ch1_v2 = publish_scenario.contents["ch1_v2"]
    ch2_v1 = publish_scenario.contents["ch2_v1"]

    target_id = _create_target(client, owner)

    # Share target with editor and viewer so we can isolate novel vs target permissions.
    for user in (editor, viewer):
        r = client.post(
            f"/publishing/targets/{target_id}/members",
            json={"userId": str(user.user_id), "role": "publisher"},
            headers=_headers(owner),
        )
        assert r.status_code == 200

    # Novel does not exist on Reader yet -> all 3 chapters (including chapter_is_public=False) are "new".
    initial = client.get(
        f"/novels/{novel.novel_id}/publish/status",
        params={"targetId": target_id},
        headers=_headers(owner),
    )
    assert initial.status_code == status.HTTP_200_OK
    data = initial.json()
    assert data["existsOnReader"] is False
    assert data["studioChapterCount"] == 3
    assert data["readerChapterCount"] == 0
    assert data["newCount"] == 3
    assert data["outdatedCount"] == 0
    assert data["upToDateCount"] == 0
    assert data["readerOnlyCount"] == 0

    # Seed Reader with ch1 outdated (v1), ch2 up-to-date (ch2_v1), ch99 reader-only.
    seeded = fake_reader.seed_novel(
        str(novel.novel_id),
        title=novel.novel_title,
        chapters={
            1: ("Ch 1", "Chapter 1 v1", str(publish_scenario.contents["ch1_v1"].chapter_content_id)),
            2: ("Ch 2", "Chapter 2 v1", str(ch2_v1.chapter_content_id)),
            99: ("Extra", "Reader only", "old-ext-ver"),
        },
    )

    # Editor with target access succeeds and sees accurate live diff (ch1_v2 != ch1_v1).
    assert ch1_v2.chapter_content_id != publish_scenario.contents["ch1_v1"].chapter_content_id
    diff_resp = client.get(
        f"/novels/{novel.novel_id}/publish/status",
        params={"targetId": target_id},
        headers=_headers(editor),
    )
    assert diff_resp.status_code == status.HTTP_200_OK
    diff = diff_resp.json()
    assert diff["existsOnReader"] is True
    assert diff["readerNovelId"] == str(seeded.novel_id)
    assert diff["studioChapterCount"] == 3
    assert diff["readerChapterCount"] == 3
    assert diff["newCount"] == 1
    assert diff["outdatedCount"] == 1
    assert diff["upToDateCount"] == 1
    assert diff["readerOnlyCount"] == 1

    # Viewer denied even with target access.
    assert (
        client.get(
            f"/novels/{novel.novel_id}/publish/status",
            params={"targetId": target_id},
            headers=_headers(viewer),
        ).status_code
        == status.HTTP_403_FORBIDDEN
    )

    # Outsider denied.
    assert (
        client.get(
            f"/novels/{novel.novel_id}/publish/status",
            params={"targetId": target_id},
            headers=_headers(outsider),
        ).status_code
        == status.HTTP_403_FORBIDDEN
    )

    # Target non-member (even if novel editor) denied.
    private_target_id = _create_target(client, owner, name="Owner Only Target")
    assert (
        client.get(
            f"/novels/{novel.novel_id}/publish/status",
            params={"targetId": private_target_id},
            headers=_headers(editor),
        ).status_code
        == status.HTTP_403_FORBIDDEN
    )


def test_start_publish_job_conflict_stale_autofail_and_queries(
    client: TestClient,
    test_db: Session,
    publish_scenario: DatabaseScenario,
    recording_publish_dispatcher: RecordingPublishDispatcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(publishing_settings, "ALLOW_PRIVATE_PUBLISH_TARGETS", True)
    monkeypatch.setattr(publishing_settings, "PUBLISH_STALE_SECONDS", 60)
    fake_reader = FakeReaderServer()
    app.dependency_overrides[get_reader_client] = lambda: ReaderClient(transport=fake_reader.transport())

    owner = publish_scenario.users["owner"]
    viewer = publish_scenario.users["viewer"]
    novel = publish_scenario.novels["novel"]

    target_id = _create_target(client, owner, name="Target A")
    target_b_id = _create_target(client, owner, name="Target B")

    # Viewer cannot start publish.
    assert (
        client.post(
            f"/novels/{novel.novel_id}/publish",
            json={"targetId": target_id, "mode": "all"},
            headers=_headers(viewer),
        ).status_code
        == status.HTTP_403_FORBIDDEN
    )

    # Range validation.
    bad_range = client.post(
        f"/novels/{novel.novel_id}/publish",
        json={"targetId": target_id, "mode": "range", "startChapter": 5, "endChapter": 2},
        headers=_headers(owner),
    )
    assert bad_range.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # Start job on Target A.
    started = client.post(
        f"/novels/{novel.novel_id}/publish",
        json={"targetId": target_id, "mode": "range", "startChapter": 1, "endChapter": 2},
        headers=_headers(owner),
    )
    assert started.status_code == status.HTTP_202_ACCEPTED
    job1 = started.json()
    assert job1["status"] == "pending"
    assert job1["mode"] == "range"
    assert job1["startChapter"] == 1
    assert job1["endChapter"] == 2
    assert recording_publish_dispatcher.jobs == [uuid.UUID(job1["jobId"])]

    # Active duplicate returns 409 Conflict.
    dup = client.post(
        f"/novels/{novel.novel_id}/publish",
        json={"targetId": target_id, "mode": "outdated"},
        headers=_headers(owner),
    )
    assert dup.status_code == status.HTTP_409_CONFLICT

    # Different target is allowed concurrently.
    other_target = client.post(
        f"/novels/{novel.novel_id}/publish",
        json={"targetId": target_b_id, "mode": "all"},
        headers=_headers(owner),
    )
    assert other_target.status_code == status.HTTP_202_ACCEPTED

    # Make job1 a stale processing job -> retrying auto-fails job1 and creates job2.
    stale_time = datetime.now(UTC) - timedelta(seconds=120)
    test_db.execute(
        update(PublishJob)
        .where(PublishJob.job_id == uuid.UUID(job1["jobId"]))
        .values(status="processing", updated_at=stale_time)
    )
    test_db.commit()

    retried = client.post(
        f"/novels/{novel.novel_id}/publish",
        json={"targetId": target_id, "mode": "outdated"},
        headers=_headers(owner),
    )
    assert retried.status_code == status.HTTP_202_ACCEPTED
    job2 = retried.json()
    assert job2["jobId"] != job1["jobId"]
    assert job2["status"] == "pending"

    # Verify job1 was marked failed.
    fetched_job1 = client.get(
        f"/novels/{novel.novel_id}/publish/jobs/{job1['jobId']}",
        headers=_headers(owner),
    )
    assert fetched_job1.status_code == status.HTTP_200_OK
    assert fetched_job1.json()["status"] == "failed"
    assert "timed out" in fetched_job1.json()["errorMessage"]

    # List jobs with and without targetId filter.
    all_jobs = client.get(f"/novels/{novel.novel_id}/publish/jobs", headers=_headers(owner)).json()
    assert len(all_jobs) == 3
    target_a_jobs = client.get(
        f"/novels/{novel.novel_id}/publish/jobs",
        params={"targetId": target_id},
        headers=_headers(owner),
    ).json()
    assert len(target_a_jobs) == 2

    # Enqueue failure marks job failed and returns 503.
    test_db.execute(
        update(PublishJob)
        .where(PublishJob.job_id == uuid.UUID(job2["jobId"]))
        .values(status="completed")
    )
    test_db.commit()
    recording_publish_dispatcher.enqueue_error = PublishEnqueueFailedException("redis unavailable")
    enqueue_fail = client.post(
        f"/novels/{novel.novel_id}/publish",
        json={"targetId": target_id, "mode": "all"},
        headers=_headers(owner),
    )
    assert enqueue_fail.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    latest_target_a = client.get(
        f"/novels/{novel.novel_id}/publish/jobs",
        params={"targetId": target_id},
        headers=_headers(owner),
    ).json()[0]
    assert latest_target_a["status"] == "failed"
    assert "redis unavailable" in latest_target_a["errorMessage"]
