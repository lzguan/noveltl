from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.auth.constants import UserType
from src.auth.models import User
from src.auth.utils import create_access_token
from src.languages.models import Language
from src.novels.constants import NovelType, Role, Visibility
from src.novels.models import Chapter, ChapterContent, Novel, NovelContributor, SourceWork
from src.translations.models import (
    TranslationBatch,
    TranslationChapterAccept,
    TranslationChapterOutput,
    TranslationJobChapter,
    TranslationStage,
)
from src.translations.schemas import TranslationJobCreate
from src.translations.tasks.jobs import create_job


@dataclass(frozen=True)
class OutputsFixture:
    editor: User
    outsider: User
    source_novel: Novel
    target_a: Novel
    target_b: Novel
    viewer_only_target: Novel
    other_work_novel: Novel
    chapters: list[Chapter]
    snapshotted_contents: list[ChapterContent]
    job_id: UUID
    batches: list[TranslationBatch]


def _auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": "Bearer " + create_access_token({"sub": user.user_name}, timedelta(minutes=5))}


async def _seed_outputs_fixture(db: AsyncSession) -> OutputsFixture:
    zh = Language(language_name="Chinese", language_code="zh")
    en = Language(language_name="English", language_code="en")
    sw_main = SourceWork(source_work_title="Main Work")
    sw_other = SourceWork(source_work_title="Other Work")
    editor = User(user_name="editor_user", user_hashed_password="x", user_type=UserType.USER)
    outsider = User(user_name="outsider_user", user_hashed_password="x", user_type=UserType.USER)
    db.add_all([zh, en, sw_main, sw_other, editor, outsider])
    await db.flush()

    source_novel = Novel(
        novel_title="Source Novel",
        novel_visibility=Visibility.PRIVATE,
        novel_type=NovelType.ORIGINAL,
        source_work_id=sw_main.source_work_id,
        language_code="zh",
    )
    target_a = Novel(
        novel_title="Target Alpha",
        novel_visibility=Visibility.PRIVATE,
        novel_type=NovelType.TRANSLATION,
        source_work_id=sw_main.source_work_id,
        language_code="en",
    )
    target_b = Novel(
        novel_title="Target Beta",
        novel_visibility=Visibility.UNLISTED,
        novel_type=NovelType.TRANSLATION,
        source_work_id=sw_main.source_work_id,
        language_code="en",
    )
    viewer_only_target = Novel(
        novel_title="Target Viewer Only",
        novel_visibility=Visibility.PUBLIC,
        novel_type=NovelType.TRANSLATION,
        source_work_id=sw_main.source_work_id,
        language_code="en",
    )
    other_work_novel = Novel(
        novel_title="Other Work Novel",
        novel_visibility=Visibility.PRIVATE,
        novel_type=NovelType.TRANSLATION,
        source_work_id=sw_other.source_work_id,
        language_code="en",
    )
    db.add_all([source_novel, target_a, target_b, viewer_only_target, other_work_novel])
    await db.flush()

    db.add_all(
        [
            NovelContributor(novel_id=source_novel.novel_id, user_id=editor.user_id, contributor_role=Role.EDITOR),
            NovelContributor(novel_id=target_a.novel_id, user_id=editor.user_id, contributor_role=Role.OWNER),
            NovelContributor(novel_id=target_b.novel_id, user_id=editor.user_id, contributor_role=Role.EDITOR),
            NovelContributor(
                novel_id=viewer_only_target.novel_id, user_id=editor.user_id, contributor_role=Role.VIEWER
            ),
            NovelContributor(novel_id=other_work_novel.novel_id, user_id=editor.user_id, contributor_role=Role.OWNER),
        ]
    )

    chapters = [
        Chapter(
            chapter_num=n,
            chapter_title=f"Source Title {n}",
            chapter_is_public=True,
            novel_id=source_novel.novel_id,
        )
        for n in (1, 2, 3, 4)
    ]
    db.add_all(chapters)
    await db.flush()

    snapshotted_contents = [
        ChapterContent(
            chapter_id=chapter.chapter_id,
            chapter_content_text=f"Snapshotted source text {chapter.chapter_num}",
            chapter_content_version=1,
        )
        for chapter in chapters
    ]
    db.add_all(snapshotted_contents)
    await db.commit()

    # Batch size 2 -> batch 0 has chapters 1, 2; batch 1 has chapters 3, 4.
    job_id = await create_job(
        db,
        TranslationJobCreate.model_validate(
            {
                "novel_id": source_novel.novel_id,
                "config": {"batch_size": 2},
                "stages": [{"action": "translate", "config": {"model": "qwen-plus"}}],
            }
        ),
    )

    # Add a newer content version to chapter 1 after job creation to prove preview reads the snapshot.
    db.add(
        ChapterContent(
            chapter_id=chapters[0].chapter_id,
            chapter_content_text="Newer edited source text 1",
            chapter_content_version=2,
        )
    )

    translate_stage = (
        await db.scalars(
            select(TranslationStage).where(
                TranslationStage.job_id == job_id,
                TranslationStage.stage_num == 1,
            )
        )
    ).one()
    batches = list(
        await db.scalars(
            select(TranslationBatch)
            .where(TranslationBatch.job_id == job_id)
            .order_by(TranslationBatch.batch_num)
        )
    )

    # Stage chapters 1, 2, 3 (leaving chapter 4 unstaged).
    db.add_all(
        [
            TranslationChapterOutput(
                job_id=job_id,
                chapter_id=chapters[i].chapter_id,
                stage_id=translate_stage.stage_id,
                translated_text=f"Translated chapter {i + 1}",
            )
            for i in range(3)
        ]
    )
    await db.commit()

    return OutputsFixture(
        editor=editor,
        outsider=outsider,
        source_novel=source_novel,
        target_a=target_a,
        target_b=target_b,
        viewer_only_target=viewer_only_target,
        other_work_novel=other_work_novel,
        chapters=chapters,
        snapshotted_contents=snapshotted_contents,
        job_id=job_id,
        batches=batches,
    )


async def test_staged_count_and_outputs_preview_endpoints(
    client: TestClient, async_test_db: AsyncSession, test_db: Session
) -> None:
    fx = await _seed_outputs_fixture(async_test_db)
    editor = fx.editor
    outsider = fx.outsider
    source_novel = fx.source_novel
    target_a = fx.target_a
    target_b = fx.target_b
    chapters = fx.chapters
    snapshotted_contents = fx.snapshotted_contents
    job_id = fx.job_id
    batches = fx.batches

    headers = _auth_headers(editor)
    outsider_headers = _auth_headers(outsider)

    # Job list & batch summary report stagedChapterCount = 3.
    jobs_resp = client.get("/translation-jobs", params={"novelId": str(source_novel.novel_id)}, headers=headers)
    assert jobs_resp.status_code == 200
    assert jobs_resp.json()["items"][0]["stagedChapterCount"] == 3

    batches_resp = client.get(f"/translation-jobs/{job_id}/batches", headers=headers)
    assert batches_resp.status_code == 200
    assert batches_resp.json()["job"]["stagedChapterCount"] == 3

    # Auth and permission checks.
    assert client.get(f"/translation-jobs/{job_id}/outputs").status_code == 401
    assert client.get(f"/translation-jobs/{job_id}/outputs", headers=outsider_headers).status_code == 404
    assert (
        client.get(f"/translation-jobs/{job_id}/outputs/{chapters[0].chapter_id}", headers=outsider_headers).status_code
        == 404
    )

    # GET /outputs returns lightweight metadata ordered by chapter_num + editable target novels.
    outputs_resp = client.get(f"/translation-jobs/{job_id}/outputs", headers=headers)
    assert outputs_resp.status_code == 200
    body = outputs_resp.json()
    assert body["lastTargetNovelId"] is None
    assert [n["novelId"] for n in body["targetNovels"]] == [str(target_a.novel_id), str(target_b.novel_id)]
    assert [
        (item["chapterId"], item["chapterNum"], item["chapterTitle"], item["batchId"], item["batchNum"])
        for item in body["items"]
    ] == [
        (str(chapters[0].chapter_id), 1, "Source Title 1", str(batches[0].batch_id), 0),
        (str(chapters[1].chapter_id), 2, "Source Title 2", str(batches[0].batch_id), 0),
        (str(chapters[2].chapter_id), 3, "Source Title 3", str(batches[1].batch_id), 1),
    ]
    for item in body["items"]:
        assert "sourceText" not in item and "translatedText" not in item
        assert item["acceptedNovelIds"] == []
        assert item["stagedAt"]

    # GET /outputs/{chapterId} returns snapshotted sourceText (v1, not newer v2) + translatedText.
    detail_resp = client.get(f"/translation-jobs/{job_id}/outputs/{chapters[0].chapter_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["chapterId"] == str(chapters[0].chapter_id)
    assert detail["chapterNum"] == 1
    assert detail["chapterTitle"] == "Source Title 1"
    assert detail["batchId"] == str(batches[0].batch_id)
    assert detail["batchNum"] == 0
    assert detail["sourceChapterContentId"] == str(snapshotted_contents[0].chapter_content_id)
    assert detail["sourceText"] == "Snapshotted source text 1"
    assert detail["translatedText"] == "Translated chapter 1"

    # Unstaged chapter 4 and unknown UUID return 404.
    assert client.get(f"/translation-jobs/{job_id}/outputs/{chapters[3].chapter_id}", headers=headers).status_code == 404
    assert client.get(f"/translation-jobs/{job_id}/outputs/{uuid4()}", headers=headers).status_code == 404


async def test_accept_scopes_skip_overwrite_provenance_and_validation(
    client: TestClient, async_test_db: AsyncSession, test_db: Session
) -> None:
    fx = await _seed_outputs_fixture(async_test_db)
    editor = fx.editor
    outsider = fx.outsider
    source_novel = fx.source_novel
    target_a = fx.target_a
    target_b = fx.target_b
    viewer_only_target = fx.viewer_only_target
    other_work_novel = fx.other_work_novel
    chapters = fx.chapters
    snapshotted_contents = fx.snapshotted_contents
    job_id = fx.job_id
    batches = fx.batches

    headers = _auth_headers(editor)
    outsider_headers = _auth_headers(outsider)
    accept_url = f"/translation-jobs/{job_id}/accept"

    # Validation & permission checks.
    assert (
        client.post(accept_url, json={"targetNovelId": str(target_a.novel_id), "scope": {"mode": "job"}}).status_code
        == 401
    )
    assert (
        client.post(
            accept_url,
            json={"targetNovelId": str(target_a.novel_id), "scope": {"mode": "job"}},
            headers=outsider_headers,
        ).status_code
        == 404
    )
    # Viewer-only target novel -> 404 (requires edit access).
    assert (
        client.post(
            accept_url,
            json={"targetNovelId": str(viewer_only_target.novel_id), "scope": {"mode": "job"}},
            headers=headers,
        ).status_code
        == 404
    )
    # Same novel as source -> 400.
    same_resp = client.post(
        accept_url,
        json={"targetNovelId": str(source_novel.novel_id), "scope": {"mode": "job"}},
        headers=headers,
    )
    assert same_resp.status_code == 400
    # Cross-source-work novel -> 400.
    cross_resp = client.post(
        accept_url,
        json={"targetNovelId": str(other_work_novel.novel_id), "scope": {"mode": "job"}},
        headers=headers,
    )
    assert cross_resp.status_code == 400
    # Invalid range (start > end) -> 422.
    bad_range_resp = client.post(
        accept_url,
        json={
            "targetNovelId": str(target_a.novel_id),
            "scope": {"mode": "range", "startChapterNum": 3, "endChapterNum": 2},
        },
        headers=headers,
    )
    assert bad_range_resp.status_code == 422
    # Empty scope (chapter 4 is unstaged) -> 400.
    empty_resp = client.post(
        accept_url,
        json={
            "targetNovelId": str(target_a.novel_id),
            "scope": {"mode": "range", "startChapterNum": 4, "endChapterNum": 4},
        },
        headers=headers,
    )
    assert empty_resp.status_code == 400
    assert empty_resp.json()["detail"] == "No staged translated chapters match the selected scope."

    # 1) Single-chapter range accept (start == end == 2) into target_a.
    r1 = client.post(
        accept_url,
        json={
            "targetNovelId": str(target_a.novel_id),
            "scope": {"mode": "range", "startChapterNum": 2, "endChapterNum": 2},
            "onExisting": "skip",
        },
        headers=headers,
    )
    assert r1.status_code == 200
    assert r1.json() == {
        "targetNovelId": str(target_a.novel_id),
        "createdChapters": 1,
        "updatedChapters": 0,
        "skippedChapters": 0,
        "chapterNums": [2],
    }

    # Verify created chapter has copied title, chapter_is_public=False, version=1.
    ch2 = test_db.scalar(
        select(Chapter).where(Chapter.novel_id == target_a.novel_id, Chapter.chapter_num == 2)
    )
    assert ch2 is not None
    assert ch2.chapter_title == "Source Title 2"
    assert ch2.chapter_is_public is False
    ch2_contents = list(
        test_db.scalars(
            select(ChapterContent)
            .where(ChapterContent.chapter_id == ch2.chapter_id)
            .order_by(ChapterContent.chapter_content_version)
        )
    )
    assert [(c.chapter_content_version, c.chapter_content_text) for c in ch2_contents] == [
        (1, "Translated chapter 2")
    ]

    # 2) Batch 0 accept (chapters 1 & 2) with onExisting="skip": ch 1 created, ch 2 skipped.
    r2 = client.post(
        accept_url,
        json={
            "targetNovelId": str(target_a.novel_id),
            "scope": {"mode": "batch", "batchId": str(batches[0].batch_id)},
            "onExisting": "skip",
        },
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json() == {
        "targetNovelId": str(target_a.novel_id),
        "createdChapters": 1,
        "updatedChapters": 0,
        "skippedChapters": 1,
        "chapterNums": [1],
    }

    # 3) Full job accept (chapters 1, 2, 3) with onExisting="overwrite": ch 3 created (v1), ch 1 & 2 updated (v2).
    r3 = client.post(
        accept_url,
        json={
            "targetNovelId": str(target_a.novel_id),
            "scope": {"mode": "job"},
            "onExisting": "overwrite",
        },
        headers=headers,
    )
    assert r3.status_code == 200
    assert r3.json() == {
        "targetNovelId": str(target_a.novel_id),
        "createdChapters": 1,
        "updatedChapters": 2,
        "skippedChapters": 0,
        "chapterNums": [1, 2, 3],
    }

    test_db.expire_all()
    target_a_chapters = list(
        test_db.scalars(
            select(Chapter).where(Chapter.novel_id == target_a.novel_id).order_by(Chapter.chapter_num)
        )
    )
    assert [c.chapter_num for c in target_a_chapters] == [1, 2, 3]
    versions_by_num = {
        c.chapter_num: list(
            test_db.scalars(
                select(ChapterContent.chapter_content_version)
                .where(ChapterContent.chapter_id == c.chapter_id)
                .order_by(ChapterContent.chapter_content_version)
            )
        )
        for c in target_a_chapters
    }
    assert versions_by_num == {1: [1, 2], 2: [1, 2], 3: [1]}

    # Verify provenance rows in translation_chapter_accepts:
    # r1 wrote ch2 (1), r2 wrote ch1 (1), r3 wrote ch1,ch2,ch3 (3) -> 5 rows total.
    target_ch = Chapter.__table__.alias("target_ch")
    accepts = list(
        test_db.execute(
            select(
                TranslationChapterAccept,
                TranslationJobChapter.chapter_num,
                TranslationJobChapter.source_chapter_content_id,
                target_ch.c.novel_id,
            )
            .join(TranslationStage, TranslationStage.stage_id == TranslationChapterAccept.stage_id)
            .join(
                TranslationJobChapter,
                and_(
                    TranslationJobChapter.job_id == TranslationStage.job_id,
                    TranslationJobChapter.chapter_id == TranslationChapterAccept.source_chapter_id,
                ),
            )
            .join(
                ChapterContent,
                ChapterContent.chapter_content_id == TranslationChapterAccept.target_chapter_content_id,
            )
            .join(target_ch, target_ch.c.chapter_id == ChapterContent.chapter_id)
            .where(TranslationStage.job_id == job_id)
            .order_by(TranslationJobChapter.chapter_num, TranslationChapterAccept.created_at)
        ).all()
    )
    assert len(accepts) == 5
    by_target_content_ids = {acc.target_chapter_content_id for acc, _, _, _ in accepts}
    all_target_content_ids = set(
        test_db.scalars(
            select(ChapterContent.chapter_content_id)
            .join(Chapter, Chapter.chapter_id == ChapterContent.chapter_id)
            .where(Chapter.novel_id == target_a.novel_id)
        )
    )
    assert by_target_content_ids == all_target_content_ids
    # Every provenance row links back via translation_job_chapters to the snapshotted source content ID.
    expected_source_content = {i + 1: snapshotted_contents[i].chapter_content_id for i in range(3)}
    for acc, chapter_num, source_content_id, target_novel_id in accepts:
        assert target_novel_id == target_a.novel_id
        assert source_content_id == expected_source_content[chapter_num]
        assert acc.source_chapter_id == chapters[chapter_num - 1].chapter_id

    # 4) Accept chapter 1 into target_b so lastTargetNovelId switches to target_b and ch 1 has both targets.
    r4 = client.post(
        accept_url,
        json={
            "targetNovelId": str(target_b.novel_id),
            "scope": {"mode": "range", "startChapterNum": 1, "endChapterNum": 1},
        },
        headers=headers,
    )
    assert r4.status_code == 200
    assert r4.json()["createdChapters"] == 1

    outputs_after = client.get(f"/translation-jobs/{job_id}/outputs", headers=headers).json()
    assert outputs_after["lastTargetNovelId"] == str(target_b.novel_id)
    accepted_by_num = {item["chapterNum"]: set(item["acceptedNovelIds"]) for item in outputs_after["items"]}
    assert accepted_by_num == {
        1: {str(target_a.novel_id), str(target_b.novel_id)},
        2: {str(target_a.novel_id)},
        3: {str(target_a.novel_id)},
    }

    # If editor loses access to target_b, lastTargetNovelId falls back to None.
    test_db.execute(
        delete(NovelContributor).where(
            NovelContributor.novel_id == target_b.novel_id,
            NovelContributor.user_id == editor.user_id,
        )
    )
    test_db.commit()
    outputs_revoked = client.get(f"/translation-jobs/{job_id}/outputs", headers=headers).json()
    assert outputs_revoked["lastTargetNovelId"] is None
    assert [n["novelId"] for n in outputs_revoked["targetNovels"]] == [str(target_a.novel_id)]


async def test_multistage_outputs_selection_and_accept(
    client: TestClient,
    test_db: Session,
    async_test_db: AsyncSession,
) -> None:
    fx = await _seed_outputs_fixture(async_test_db)
    headers = _auth_headers(fx.editor)
    job_id = await create_job(
        async_test_db,
        TranslationJobCreate.model_validate(
            {
                "novel_id": fx.source_novel.novel_id,
                "config": {"batch_size": 10},
                "stages": [
                    {"action": "translate", "config": {"model": "qwen-plus"}},
                    {"action": "translate", "config": {"model": "qwen-plus"}},
                ],
            }
        ),
    )
    test_db.expire_all()
    translate_stages = list(
        test_db.scalars(
            select(TranslationStage)
            .where(TranslationStage.job_id == job_id, TranslationStage.action == "translate")
            .order_by(TranslationStage.stage_num)
        )
    )
    assert len(translate_stages) == 2
    stage_1, stage_2 = translate_stages

    for idx, ch in enumerate(fx.chapters, start=1):
        test_db.add(
            TranslationChapterOutput(
                job_id=job_id,
                stage_id=stage_1.stage_id,
                chapter_id=ch.chapter_id,
                translated_text=f"Stage 1 text {idx}",
            )
        )
        test_db.add(
            TranslationChapterOutput(
                job_id=job_id,
                stage_id=stage_2.stage_id,
                chapter_id=ch.chapter_id,
                translated_text=f"Stage 2 text {idx}",
            )
        )
    test_db.commit()

    # stagedChapterCount counts distinct chapters (4), not 8 stage-chapter rows.
    jobs_resp = client.get("/translation-jobs", params={"novelId": str(fx.source_novel.novel_id)}, headers=headers)
    assert jobs_resp.status_code == 200
    by_job_id = {item["jobId"]: item for item in jobs_resp.json()["items"]}
    assert by_job_id[str(job_id)]["stagedChapterCount"] == len(fx.chapters)

    # Default GET /outputs selects the latest staged stage (stage 2) and lists both stages.
    default_outputs = client.get(f"/translation-jobs/{job_id}/outputs", headers=headers)
    assert default_outputs.status_code == 200
    default_body = default_outputs.json()
    assert default_body["selectedStageId"] == str(stage_2.stage_id)
    assert [(s["stageId"], s["stageNum"], s["chapterCount"]) for s in default_body["stages"]] == [
        (str(stage_1.stage_id), 1, len(fx.chapters)),
        (str(stage_2.stage_id), 2, len(fx.chapters)),
    ]

    # Explicit ?stageId selects stage 1; unknown stage returns 404.
    assert client.get(f"/translation-jobs/{job_id}/outputs", params={"stageId": str(uuid4())}, headers=headers).status_code == 404
    stage1_outputs = client.get(
        f"/translation-jobs/{job_id}/outputs", params={"stageId": str(stage_1.stage_id)}, headers=headers
    )
    assert stage1_outputs.status_code == 200
    assert stage1_outputs.json()["selectedStageId"] == str(stage_1.stage_id)

    ch1_id = fx.chapters[0].chapter_id
    d_default = client.get(f"/translation-jobs/{job_id}/outputs/{ch1_id}", headers=headers)
    assert d_default.status_code == 200
    assert d_default.json()["stageId"] == str(stage_2.stage_id)
    assert d_default.json()["translatedText"] == "Stage 2 text 1"

    d_stage1 = client.get(
        f"/translation-jobs/{job_id}/outputs/{ch1_id}", params={"stageId": str(stage_1.stage_id)}, headers=headers
    )
    assert d_stage1.status_code == 200
    assert d_stage1.json()["stageId"] == str(stage_1.stage_id)
    assert d_stage1.json()["stageNum"] == 1
    assert d_stage1.json()["translatedText"] == "Stage 1 text 1"

    # Accept stage 1 explicitly into target_a and confirm text + stage_id provenance.
    accept_resp = client.post(
        f"/translation-jobs/{job_id}/accept",
        json={
            "targetNovelId": str(fx.target_a.novel_id),
            "stageId": str(stage_1.stage_id),
            "scope": {"mode": "range", "startChapterNum": 1, "endChapterNum": 1},
        },
        headers=headers,
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["createdChapters"] == 1

    target_text = test_db.scalar(
        select(ChapterContent.chapter_content_text)
        .join(Chapter, Chapter.chapter_id == ChapterContent.chapter_id)
        .where(Chapter.novel_id == fx.target_a.novel_id, Chapter.chapter_num == 1)
    )
    assert target_text == "Stage 1 text 1"

    accept_row = test_db.scalar(
        select(TranslationChapterAccept)
        .join(TranslationStage, TranslationStage.stage_id == TranslationChapterAccept.stage_id)
        .where(TranslationStage.job_id == job_id)
    )
    assert accept_row is not None
    assert accept_row.stage_id == stage_1.stage_id

    # acceptedNovelIds is scoped to the selected stage.
    stage1_after = client.get(
        f"/translation-jobs/{job_id}/outputs", params={"stageId": str(stage_1.stage_id)}, headers=headers
    ).json()
    stage2_after = client.get(
        f"/translation-jobs/{job_id}/outputs", params={"stageId": str(stage_2.stage_id)}, headers=headers
    ).json()
    assert stage1_after["items"][0]["acceptedNovelIds"] == [str(fx.target_a.novel_id)]
    assert stage2_after["items"][0]["acceptedNovelIds"] == []
