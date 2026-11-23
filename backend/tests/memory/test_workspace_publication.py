from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, event, func, insert, inspect, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

from src.memory.access import write_continuity_summary
from src.memory.agent.tasks import tasks
from src.memory.agent.tasks.jobs import claim_job, claim_task
from src.memory.agent.tasks.schedule import StageBarrierSchedule
from src.memory.exceptions import MemoryJobClaimLostException
from src.memory.models import Memory, MemoryChapterTask, MemoryJob
from src.memory.plugins.conventions.access import create_convention, delete_convention, update_convention
from src.memory.plugins.conventions.models import TranslationConvention
from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.plugins.glossary import access
from src.memory.plugins.glossary.models import GlossaryAssociation, GlossaryTerm
from src.memory.plugins.translations.access import create_term_translation
from src.memory.plugins.translations.models import TermTranslation
from src.memory.shadow_models import (
    MemoryWorkspace,
    ShadowConvention,
    ShadowGlossaryAssociation,
    ShadowMemory,
    ShadowTerm,
    ShadowTermTranslation,
)
from src.memory.types import Creator, JobStatus, MemoryType, ReviewStatus
from src.memory.workspaces import discard_workspace, publish_workspace
from src.model_base import Base
from tests.fixtures.memory_workspaces import ReadScenario
from tests.fixtures.memory_workspaces import reads as reads


async def _row[T: Base](db: AsyncSession, model: type[T], key: Any) -> T:
    row = await db.get(model, key)
    assert row is not None
    return row


async def _draft(db: AsyncSession, reads: ReadScenario):
    term = await access.create_term(db, reads.current.memory_group_id, "Alpha", workspace_id=reads.workspace_id)
    memory, _ = await access.create_memory(db, reads.current, Creator.AGENT, MemoryType.FACT, ["Alpha"], "Draft fact.")
    return term.term_id, memory.memory_id


async def _claimed(db: AsyncSession, reads: ReadScenario):
    workspace = await db.get(MemoryWorkspace, reads.workspace_id)
    assert workspace is not None
    task = tasks.ClaimedTask(workspace.memory_job_id, workspace.chapter_id, workspace.stage_num)
    token = uuid4()
    assert await claim_job(db, task.memory_job_id, token, timedelta(minutes=5)) is not None
    assert (
        await claim_task(
            db, task.memory_job_id, task.chapter_id, token, StageBarrierSchedule(), stage_num=task.stage_num
        )
        is not None
    )
    result = tasks.CompletedMemoryTask(
        task.memory_job_id,
        reads.current.memory_group_id,
        reads.current.chapter_id,
        reads.current.chapter_content_id,
        2,
        None,
        workspace_id=reads.workspace_id,
    )
    return task, token, result


@pytest.fixture
async def publication_token(async_test_db: AsyncSession, reads: ReadScenario) -> UUID:
    return (await _claimed(async_test_db, reads))[1]


async def _publish(db: AsyncSession, reads: ReadScenario, token: UUID) -> None:
    await publish_workspace(db, reads.workspace_id, token)


async def test_publication_commits_in_final_request_and_cleanup_is_separate(
    testing_session_local: sessionmaker[Session],
    async_test_db: AsyncSession,
    reads: ReadScenario,
    publication_token: UUID,
):
    term_id, memory_id = await _draft(async_test_db, reads)
    await create_term_translation(async_test_db, reads.current, "Alpha", "Alpha rendering")
    await create_convention(
        async_test_db,
        reads.current.memory_group_id,
        workspace_id=reads.workspace_id,
        category=ConventionCategory.NAMING,
        title="Names",
        rule="Preserve forms.",
        rationale=None,
        creator_type=Creator.AGENT,
    )
    await write_continuity_summary(async_test_db, reads.current, "Handoff.")
    workspace_id = reads.workspace_id
    assert workspace_id is not None
    original_expiry = await async_test_db.scalar(
        select(MemoryJob.claim_expires_at).where(MemoryJob.claim_token == publication_token)
    )
    await async_test_db.commit()
    requests = []
    committed = []
    engine = async_test_db.get_bind().engine

    def before_query(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.startswith("/* workspace:"):
            requests.append(statement)
            with testing_session_local() as other:
                assert other.scalar(select(func.count()).select_from(Memory)) == 0

    def after_query(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.startswith("/* workspace:complete */"):
            with testing_session_local() as other:
                committed.append(other.scalar(select(func.count()).select_from(Memory)))

    event.listen(engine, "before_cursor_execute", before_query)
    event.listen(engine, "after_cursor_execute", after_query)
    try:
        await _publish(async_test_db, reads, publication_token)
    finally:
        event.remove(engine, "before_cursor_execute", before_query)
        event.remove(engine, "after_cursor_execute", after_query)
    assert requests[-1].rstrip().endswith("COMMIT;")
    assert committed == [2]
    async with AsyncSession(async_test_db.bind) as other:
        assert (
            await other.scalar(select(MemoryJob.claim_expires_at).where(MemoryJob.claim_token == publication_token))
            == original_expiry
        )
        assert (await _row(other, Memory, memory_id)).memory_content == "Draft fact."
        assert (await _row(other, GlossaryTerm, term_id)).term == "Alpha"
        assert (await _row(other, TermTranslation, term_id)).translation == "Alpha rendering"
        assert await other.scalar(select(func.count()).select_from(GlossaryAssociation)) == 1
        assert await other.scalar(select(func.count()).select_from(TranslationConvention)) == 1
        assert await other.scalar(select(func.count()).select_from(Memory)) == 2
        assert await other.get(MemoryWorkspace, workspace_id) is not None
    await discard_workspace(async_test_db, workspace_id)
    await async_test_db.commit()
    assert await async_test_db.get(MemoryWorkspace, workspace_id) is None
    assert await async_test_db.get(Memory, memory_id) is not None


async def test_publication_copies_every_shadow_column_over_existing_rows(
    testing_session_local: sessionmaker[Session],
    async_test_db: AsyncSession,
    reads: ReadScenario,
    publication_token: UUID,
):
    await _draft(async_test_db, reads)
    await create_term_translation(async_test_db, reads.current, "Alpha", "Draft rendering")
    await create_convention(
        async_test_db,
        reads.current.memory_group_id,
        workspace_id=reads.workspace_id,
        category=ConventionCategory.NAMING,
        title="Names",
        rule="Draft rule.",
        rationale=None,
        creator_type=Creator.AGENT,
    )
    tables = (
        (GlossaryTerm, ShadowTerm),
        (Memory, ShadowMemory),
        (TermTranslation, ShadowTermTranslation),
        (TranslationConvention, ShadowConvention),
        (GlossaryAssociation, ShadowGlossaryAssociation),
    )
    expected = {}
    for model, shadow in tables:
        columns = [column.name for column in inspect(model).columns]
        payloads = [
            {column: getattr(row, column) for column in columns}
            for row in await async_test_db.scalars(select(shadow).where(shadow.workspace_id == reads.workspace_id))
        ]
        assert len(payloads) == 1
        expected[model] = payloads
        await async_test_db.execute(insert(model), payloads)
        await async_test_db.execute(update(model).values(updated_at=datetime(2099, 1, 1)))
    await async_test_db.commit()

    await _publish(async_test_db, reads, publication_token)
    with testing_session_local() as other:
        for model, _shadow in tables:
            actual = [dict(row) for row in other.execute(select(*inspect(model).columns)).mappings()]
            assert actual == expected[model]


async def test_staged_memory_overwrites_content_and_review_changed_after_staging(
    async_test_db: AsyncSession,
    reads: ReadScenario,
    publication_token: UUID,
):
    await access.create_term(async_test_db, reads.published.memory_group_id, "Alpha")
    original, _ = await access.create_memory(
        async_test_db, reads.predecessor, Creator.AGENT, MemoryType.FACT, ["Alpha"], "Original."
    )
    await access.expire_memory(async_test_db, reads.current, original.memory_id, [MemoryType.FACT])
    original.memory_content = "Human correction."
    original.memory_review_status = ReviewStatus.APPROVED
    await async_test_db.commit()
    await _publish(async_test_db, reads, publication_token)
    await async_test_db.refresh(original)
    assert original.memory_end_num == 2
    assert original.memory_content == "Original." and original.memory_review_status == ReviewStatus.PENDING


async def test_supersession_publishes_final_ids_and_convention_tombstones(
    async_test_db: AsyncSession,
    reads: ReadScenario,
    publication_token: UUID,
):
    await access.create_term(async_test_db, reads.published.memory_group_id, "Alpha")
    original, _ = await access.create_memory(
        async_test_db, reads.predecessor, Creator.AGENT, MemoryType.DEFINITION, ["Alpha"], "Old definition."
    )
    original_id = original.memory_id
    replacement, _ = await access.supersede_memory(
        async_test_db, reads.current, original.memory_id, Creator.AGENT, MemoryType.DEFINITION, "New definition."
    )
    replacement_id = replacement.memory_id
    convention = await create_convention(
        async_test_db,
        reads.published.memory_group_id,
        category=ConventionCategory.NAMING,
        title="Old guidance",
        rule="Withdraw this.",
        rationale=None,
        creator_type=Creator.AGENT,
    )
    convention_id = convention.convention_id
    await delete_convention(
        async_test_db,
        reads.current.memory_group_id,
        convention_id,
        workspace_id=reads.workspace_id,
        only_creator=Creator.AGENT,
        only_pending=True,
    )
    convention.review_status = ReviewStatus.APPROVED
    await async_test_db.commit()
    await _publish(async_test_db, reads, publication_token)
    published = await _row(async_test_db, Memory, replacement_id)
    assert published.supersedes_memory_id == original_id
    await async_test_db.refresh(original)
    assert original.memory_end_num == 2 and published.memory_start_num == 2
    assert await async_test_db.get(TranslationConvention, convention_id) is None
    page = await access.inspect_terms(async_test_db, reads.published, ["Alpha"], [MemoryType.DEFINITION])
    assert [row.memory.memory_id for row in page.rows] == [replacement_id]


async def test_late_term_collision_rolls_back_every_published_change(
    async_test_db: AsyncSession,
    reads: ReadScenario,
    publication_token: UUID,
):
    await _draft(async_test_db, reads)
    await create_convention(
        async_test_db,
        reads.current.memory_group_id,
        workspace_id=reads.workspace_id,
        category=ConventionCategory.NAMING,
        title="Names",
        rule="Preserve forms.",
        rationale=None,
        creator_type=Creator.AGENT,
    )
    await access.create_term(async_test_db, reads.published.memory_group_id, "Alpha")
    await async_test_db.commit()
    with pytest.raises(IntegrityError):
        await _publish(async_test_db, reads, publication_token)
    await async_test_db.rollback()
    assert await async_test_db.scalar(select(func.count()).select_from(Memory)) == 0
    assert await async_test_db.scalar(select(func.count()).select_from(TranslationConvention)) == 0
    assert await async_test_db.get(MemoryWorkspace, reads.workspace_id) is not None


async def test_missing_association_parent_rolls_back_new_memories(
    async_test_db: AsyncSession,
    reads: ReadScenario,
    publication_token: UUID,
):
    term = await access.create_term(async_test_db, reads.published.memory_group_id, "Alpha")
    await access.create_memory(async_test_db, reads.current, Creator.AGENT, MemoryType.FACT, ["Alpha"], "Draft fact.")
    await async_test_db.execute(delete(GlossaryTerm).where(GlossaryTerm.term_id == term.term_id))
    await async_test_db.commit()
    with pytest.raises(IntegrityError):
        await _publish(async_test_db, reads, publication_token)
    await async_test_db.rollback()
    assert await async_test_db.scalar(select(func.count()).select_from(Memory)) == 0


async def test_staged_translations_and_summaries_overwrite_late_reviews(
    async_test_db: AsyncSession,
    reads: ReadScenario,
    publication_token: UUID,
):
    term = await access.create_term(async_test_db, reads.published.memory_group_id, "Alpha")
    mapping = TermTranslation(
        term_id=term.term_id, translation="Rejected", review_status=ReviewStatus.REJECTED, creator_type=Creator.USER
    )
    async_test_db.add(mapping)
    await async_test_db.flush()
    await create_term_translation(async_test_db, reads.current, "Alpha", "Draft rendering")
    await write_continuity_summary(async_test_db, reads.published, "Original handoff.")
    await write_continuity_summary(async_test_db, reads.current, "Draft handoff.")
    summary = (await async_test_db.scalars(select(Memory).where(Memory.plugin_name == "continuity"))).one()
    summary.memory_review_status = ReviewStatus.APPROVED
    mapping.translation, mapping.review_status = "Approved rendering", ReviewStatus.APPROVED
    await async_test_db.commit()
    await _publish(async_test_db, reads, publication_token)
    await async_test_db.refresh(mapping)
    await async_test_db.refresh(summary)
    assert mapping.translation == "Draft rendering" and mapping.review_status == ReviewStatus.PENDING
    assert summary.memory_content == "Draft handoff." and summary.memory_review_status == ReviewStatus.PENDING


async def test_staged_conventions_overwrite_late_reviews(
    async_test_db: AsyncSession, reads: ReadScenario, publication_token: UUID
):
    convention = await create_convention(
        async_test_db,
        reads.published.memory_group_id,
        category=ConventionCategory.NAMING,
        title="Names",
        rule="Original.",
        rationale=None,
        creator_type=Creator.AGENT,
    )
    await update_convention(
        async_test_db,
        reads.current.memory_group_id,
        convention.convention_id,
        workspace_id=reads.workspace_id,
        category=ConventionCategory.NAMING,
        title="Names",
        rule="Draft.",
        rationale=None,
        only_pending=True,
        only_creator=Creator.AGENT,
        recorded_on=reads.current.chapter_content_id,
    )
    convention.review_status = ReviewStatus.APPROVED
    await async_test_db.commit()
    await _publish(async_test_db, reads, publication_token)
    await async_test_db.refresh(convention)
    assert convention.rule == "Draft." and convention.review_status == ReviewStatus.PENDING


async def test_unrelated_database_exception_is_not_reported_as_lost_claim(
    async_test_db: AsyncSession, reads: ReadScenario, publication_token: UUID
):
    term_id, _ = await _draft(async_test_db, reads)
    await async_test_db.commit()
    table = GlossaryTerm.__tablename__
    await async_test_db.execute(
        text(
            "CREATE FUNCTION reject_publication() RETURNS trigger LANGUAGE plpgsql AS "
            "$$ BEGIN RAISE EXCEPTION 'unrelated failure'; END $$"
        )
    )
    await async_test_db.execute(
        text(f'CREATE TRIGGER reject_publication BEFORE INSERT ON "{table}" EXECUTE FUNCTION reject_publication()')
    )
    await async_test_db.commit()
    try:
        with pytest.raises(DBAPIError) as raised:
            await _publish(async_test_db, reads, publication_token)
    finally:
        await async_test_db.rollback()
        await async_test_db.execute(text("DROP FUNCTION reject_publication() CASCADE"))
        await async_test_db.commit()
    assert getattr(raised.value.orig, "sqlstate", None) == "P0001"
    assert await async_test_db.get(GlossaryTerm, term_id) is None


@pytest.mark.parametrize("claim_lost", ["expired", "replaced"])
async def test_lost_claim_cannot_publish_committed_drafts(
    async_test_db: AsyncSession,
    reads: ReadScenario,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    claim_lost: str,
):
    task, token, result = await _claimed(async_test_db, reads)
    term_id, memory_id = await _draft(async_test_db, reads)
    await async_test_db.commit()
    values = (
        {"claim_token": uuid4()}
        if claim_lost == "replaced"
        else {"claim_expires_at": func.now() - timedelta(seconds=1)}
    )
    await async_test_db.execute(update(MemoryJob).where(MemoryJob.memory_job_id == task.memory_job_id).values(**values))
    await async_test_db.commit()
    await async_test_db.rollback()
    with pytest.raises(MemoryJobClaimLostException):
        await tasks._complete_workspace_task(async_test_db, task, result, token, testing_async_session_local)
    assert await async_test_db.get(Memory, memory_id) is None and await async_test_db.get(GlossaryTerm, term_id) is None
    assert (
        await _row(async_test_db, MemoryChapterTask, (task.memory_job_id, task.chapter_id, task.stage_num))
    ).task_status == JobStatus.PROCESSING


async def test_cleanup_failure_leaves_completed_publication_and_safe_leftovers(
    async_test_db: AsyncSession,
    reads: ReadScenario,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
):
    task, token, result = await _claimed(async_test_db, reads)
    term_id, memory_id = await _draft(async_test_db, reads)
    await async_test_db.commit()

    def fail_cleanup(_db, _workspace_id):
        raise RuntimeError("cleanup unavailable")

    monkeypatch.setattr(tasks, "discard_workspace", fail_cleanup)
    await tasks._complete_workspace_task(async_test_db, task, result, token, testing_async_session_local)
    assert (
        await async_test_db.get(Memory, memory_id) is not None
        and await async_test_db.get(GlossaryTerm, term_id) is not None
    )
    assert (
        await _row(async_test_db, MemoryChapterTask, (task.memory_job_id, task.chapter_id, task.stage_num))
    ).task_status == JobStatus.COMPLETED
    assert await async_test_db.get(MemoryWorkspace, reads.workspace_id) is not None
    await async_test_db.rollback()
    with pytest.raises(MemoryJobClaimLostException):
        await tasks._complete_workspace_task(async_test_db, task, result, token, testing_async_session_local)
    assert await async_test_db.scalar(select(func.count()).select_from(Memory)) == 1


async def test_lost_commit_acknowledgement_uses_persisted_task_state(
    async_test_db: AsyncSession,
    reads: ReadScenario,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
):
    task, token, result = await _claimed(async_test_db, reads)
    term_id, memory_id = await _draft(async_test_db, reads)
    await async_test_db.commit()
    engine = async_test_db.get_bind().engine
    lost = False

    def lose_ack(_conn, _cursor, statement, _params, _context, _many):
        nonlocal lost
        if statement.startswith("/* workspace:complete */") and not lost:
            lost = True
            raise ConnectionError("commit acknowledgement lost")

    event.listen(engine, "after_cursor_execute", lose_ack)
    try:
        await tasks._complete_workspace_task(async_test_db, task, result, token, testing_async_session_local)
    finally:
        event.remove(engine, "after_cursor_execute", lose_ack)
    assert lost
    assert (
        await async_test_db.get(Memory, memory_id) is not None
        and await async_test_db.get(GlossaryTerm, term_id) is not None
    )
    assert await async_test_db.get(MemoryWorkspace, reads.workspace_id) is None
    assert await async_test_db.scalar(select(func.count()).select_from(Memory)) == 1
