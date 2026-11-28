import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.config import publishing_settings
from src.novels.constants import Role, Visibility
from src.publishing.client import ReaderClient
from src.publishing.models import PublishingTarget, PublishJob, UserPublishingTarget
from src.publishing.processing import process_publish_job
from src.publishing.security import encrypt_api_key, extract_key_prefix
from test_support.publishing import FakeReaderServer
from test_support.test_data.scenarios import DatabaseScenario, PasswordHash, ScenarioBuilder


@pytest.fixture
def worker_scenario(test_db: Session, no_hash: PasswordHash) -> tuple[DatabaseScenario, PublishingTarget]:
    builder = ScenarioBuilder(test_db, no_hash)
    builder.language("en", "English", "en")
    builder.user("owner", "w_owner", "pass")
    builder.source_work("sw", "Worker Source Work")
    builder.novel(
        "novel",
        title="Worker Novel",
        language="en",
        source_work="sw",
        visibility=Visibility.PRIVATE,
        description="Novel summary",
        author="Novel Author",
    )
    builder.contributor("owner", novel="novel", user="owner", role=Role.OWNER)

    for num in range(1, 6):
        builder.chapter(
            f"ch{num}",
            novel="novel",
            number=num,
            title=f"Chapter {num}",
            is_public=(num % 2 == 0),
        )
        builder.content(f"ch{num}_v1", chapter=f"ch{num}", version=1, text=f"Old text {num}")
        builder.content(f"ch{num}_v2", chapter=f"ch{num}", version=2, text=f"Latest text {num}")

    scenario = builder.finish()

    api_key = "rapi_test_secret_key_1234567890"
    target = PublishingTarget(
        name="Worker Target",
        api_base_url="http://reader-api:8001",
        public_base_url="https://reader.example.com",
        encrypted_api_key=encrypt_api_key(api_key),
        key_prefix=extract_key_prefix(api_key),
        created_by_user_id=scenario.users["owner"].user_id,
    )
    test_db.add(target)
    test_db.flush()
    test_db.add(
        UserPublishingTarget(
            target_id=target.target_id,
            user_id=scenario.users["owner"].user_id,
            role="owner",
        )
    )
    test_db.commit()
    return scenario, target


async def test_worker_all_mode_chunked_sync_and_atomic_claim(
    test_db: Session,
    async_test_db: AsyncSession,
    worker_scenario: tuple[DatabaseScenario, PublishingTarget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(publishing_settings, "ALLOW_PRIVATE_PUBLISH_TARGETS", True)
    scenario, target = worker_scenario
    novel = scenario.novels["novel"]
    fake_reader = FakeReaderServer()
    reader_client = ReaderClient(transport=fake_reader.transport())

    job = PublishJob(
        novel_id=novel.novel_id,
        target_id=target.target_id,
        initiated_by_user_id=scenario.users["owner"].user_id,
        status="pending",
        mode="all",
        include_novel_metadata=True,
    )
    test_db.add(job)
    test_db.commit()

    finished = await process_publish_job(async_test_db, job.job_id, reader_client=reader_client, chunk_size=2)
    assert finished is not None
    assert finished.status == "completed"
    assert finished.total_chapters == 5
    assert finished.synced_chapters == 5
    assert finished.cursor_chapter_num == 5
    assert finished.reader_novel_id is not None
    assert finished.public_url == f"https://reader.example.com/novels/{finished.reader_novel_id}"
    assert finished.completed_at is not None

    # 3 chunks: [1, 2], [3, 4], [5]; novel metadata only sent on chunk 1.
    sync_calls = [req for req in fake_reader.requests if req[0] == "POST" and req[1].endswith("/sync")]
    assert len(sync_calls) == 3
    assert sync_calls[0][2] is not None and sync_calls[0][2]["novel"] == {
        "title": "Worker Novel",
        "description": "Novel summary",
        "author": "Novel Author",
        "languageCode": "en",
    }
    assert sync_calls[1][2] is not None and sync_calls[1][2]["novel"] is None
    assert sync_calls[2][2] is not None and sync_calls[2][2]["novel"] is None

    reader_novel = fake_reader.novels[str(novel.novel_id)]
    assert sorted(reader_novel.chapters.keys()) == [1, 2, 3, 4, 5]
    for num in range(1, 6):
        ch = reader_novel.chapters[num]
        assert ch["body"] == f"Latest text {num}"
        assert ch["externalVersion"] == str(scenario.contents[f"ch{num}_v2"].chapter_content_id)

    # Re-claiming an already completed job returns None and sends no extra requests.
    request_count_before = len(fake_reader.requests)
    assert await process_publish_job(async_test_db, job.job_id, reader_client=reader_client) is None
    assert len(fake_reader.requests) == request_count_before


async def test_worker_range_mode(
    test_db: Session,
    async_test_db: AsyncSession,
    worker_scenario: tuple[DatabaseScenario, PublishingTarget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(publishing_settings, "ALLOW_PRIVATE_PUBLISH_TARGETS", True)
    scenario, target = worker_scenario
    novel = scenario.novels["novel"]
    fake_reader = FakeReaderServer()
    reader_client = ReaderClient(transport=fake_reader.transport())

    job = PublishJob(
        novel_id=novel.novel_id,
        target_id=target.target_id,
        initiated_by_user_id=scenario.users["owner"].user_id,
        status="pending",
        mode="range",
        start_chapter=2,
        end_chapter=4,
        include_novel_metadata=True,
    )
    test_db.add(job)
    test_db.commit()

    finished = await process_publish_job(async_test_db, job.job_id, reader_client=reader_client, chunk_size=10)
    assert finished is not None
    assert finished.status == "completed"
    assert finished.total_chapters == 3
    assert finished.synced_chapters == 3
    assert finished.cursor_chapter_num == 4
    assert sorted(fake_reader.novels[str(novel.novel_id)].chapters.keys()) == [2, 3, 4]


async def test_worker_outdated_mode_and_metadata_only_sync(
    test_db: Session,
    async_test_db: AsyncSession,
    worker_scenario: tuple[DatabaseScenario, PublishingTarget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(publishing_settings, "ALLOW_PRIVATE_PUBLISH_TARGETS", True)
    scenario, target = worker_scenario
    novel = scenario.novels["novel"]
    fake_reader = FakeReaderServer()
    reader_client = ReaderClient(transport=fake_reader.transport())

    # Seed Reader: ch1 & ch2 up-to-date, ch3 outdated (v1), ch4 & ch5 missing.
    fake_reader.seed_novel(
        str(novel.novel_id),
        title="Old Title",
        chapters={
            1: ("Chapter 1", "Latest text 1", str(scenario.contents["ch1_v2"].chapter_content_id)),
            2: ("Chapter 2", "Latest text 2", str(scenario.contents["ch2_v2"].chapter_content_id)),
            3: ("Chapter 3", "Old text 3", str(scenario.contents["ch3_v1"].chapter_content_id)),
        },
    )

    job = PublishJob(
        novel_id=novel.novel_id,
        target_id=target.target_id,
        initiated_by_user_id=scenario.users["owner"].user_id,
        status="pending",
        mode="outdated",
        include_novel_metadata=True,
    )
    test_db.add(job)
    test_db.commit()

    finished = await process_publish_job(async_test_db, job.job_id, reader_client=reader_client, chunk_size=2)
    assert finished is not None
    assert finished.status == "completed"
    assert finished.total_chapters == 3
    assert finished.synced_chapters == 3
    sync_calls = [req for req in fake_reader.requests if req[0] == "POST" and req[1].endswith("/sync")]
    synced_nums = [item["chapterNum"] for _, _, body in sync_calls if body for item in body["upserts"]]
    assert synced_nums == [3, 4, 5]

    # Now everything is up-to-date; another outdated job with include_novel_metadata=True sends metadata-only sync.
    fake_reader.requests.clear()
    meta_job = PublishJob(
        novel_id=novel.novel_id,
        target_id=target.target_id,
        initiated_by_user_id=scenario.users["owner"].user_id,
        status="pending",
        mode="outdated",
        include_novel_metadata=True,
    )
    test_db.add(meta_job)
    test_db.commit()

    meta_finished = await process_publish_job(async_test_db, meta_job.job_id, reader_client=reader_client)
    assert meta_finished is not None
    assert meta_finished.status == "completed"
    assert meta_finished.total_chapters == 0
    assert meta_finished.synced_chapters == 0
    meta_syncs = [req for req in fake_reader.requests if req[0] == "POST" and req[1].endswith("/sync")]
    assert len(meta_syncs) == 1
    assert meta_syncs[0][2] is not None
    assert meta_syncs[0][2]["novel"]["title"] == "Worker Novel"
    assert meta_syncs[0][2]["upserts"] == []


async def test_worker_records_partial_progress_on_chunk_failure(
    test_db: Session,
    async_test_db: AsyncSession,
    worker_scenario: tuple[DatabaseScenario, PublishingTarget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(publishing_settings, "ALLOW_PRIVATE_PUBLISH_TARGETS", True)
    scenario, target = worker_scenario
    novel = scenario.novels["novel"]
    fake_reader = FakeReaderServer()
    fake_reader.fail_on_sync_call = 2
    reader_client = ReaderClient(transport=fake_reader.transport())

    job = PublishJob(
        novel_id=novel.novel_id,
        target_id=target.target_id,
        initiated_by_user_id=scenario.users["owner"].user_id,
        status="pending",
        mode="all",
        include_novel_metadata=True,
    )
    test_db.add(job)
    test_db.commit()

    failed = await process_publish_job(async_test_db, job.job_id, reader_client=reader_client, chunk_size=2)
    assert failed is not None
    assert failed.status == "failed"
    assert failed.total_chapters == 5
    assert failed.synced_chapters == 2
    assert failed.cursor_chapter_num == 2
    assert failed.error_message is not None
    assert "500" in failed.error_message
    assert failed.completed_at is not None
