from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, event, func, insert, inspect, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
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


def _row[T: Base](db: Session, model: type[T], key: Any) -> T:
    row = db.get(model, key)
    assert row is not None
    return row


def _draft(db: Session, reads: ReadScenario):
    term = access.create_term(db, reads.current.memory_group_id, "Alpha", workspace_id=reads.workspace_id)
    memory, _ = access.create_memory(db, reads.current, Creator.AGENT, MemoryType.FACT, ["Alpha"], "Draft fact.")
    return term.term_id, memory.memory_id


def _claimed(db: Session, reads: ReadScenario):
    workspace = db.get(MemoryWorkspace, reads.workspace_id)
    assert workspace is not None
    task = tasks.ClaimedTask(workspace.memory_job_id, workspace.chapter_id, workspace.stage_num)
    token = uuid4()
    assert claim_job(db, task.memory_job_id, token, timedelta(minutes=5)) is not None
    assert (
        claim_task(db, task.memory_job_id, task.chapter_id, token, StageBarrierSchedule(), stage_num=task.stage_num)
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
def publication_token(test_db: Session, reads: ReadScenario) -> UUID:
    return _claimed(test_db, reads)[1]


def _publish(db: Session, reads: ReadScenario, token: UUID) -> None:
    publish_workspace(db, reads.workspace_id, token)


def test_publication_commits_in_final_request_and_cleanup_is_separate(
    test_db: Session,
    reads: ReadScenario,
    publication_token: UUID,
):
    term_id, memory_id = _draft(test_db, reads)
    create_term_translation(test_db, reads.current, "Alpha", "Alpha rendering")
    create_convention(
        test_db,
        reads.current.memory_group_id,
        workspace_id=reads.workspace_id,
        category=ConventionCategory.NAMING,
        title="Names",
        rule="Preserve forms.",
        rationale=None,
        creator_type=Creator.AGENT,
    )
    write_continuity_summary(test_db, reads.current, "Handoff.")
    workspace_id = reads.workspace_id
    assert workspace_id is not None
    original_expiry = test_db.scalar(
        select(MemoryJob.claim_expires_at).where(MemoryJob.claim_token == publication_token)
    )
    test_db.commit()
    requests = []
    committed = []
    engine = test_db.get_bind().engine

    def before_query(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.startswith("/* workspace:"):
            requests.append(statement)
            with Session(bind=engine) as other:
                assert other.scalar(select(func.count()).select_from(Memory)) == 0

    def after_query(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.startswith("/* workspace:complete */"):
            with Session(bind=engine) as other:
                committed.append(other.scalar(select(func.count()).select_from(Memory)))

    event.listen(engine, "before_cursor_execute", before_query)
    event.listen(engine, "after_cursor_execute", after_query)
    try:
        _publish(test_db, reads, publication_token)
    finally:
        event.remove(engine, "before_cursor_execute", before_query)
        event.remove(engine, "after_cursor_execute", after_query)
    assert requests[-1].rstrip().endswith("COMMIT;")
    assert committed == [2]
    with Session(bind=test_db.get_bind()) as other:
        assert (
            other.scalar(select(MemoryJob.claim_expires_at).where(MemoryJob.claim_token == publication_token))
            == original_expiry
        )
        assert _row(other, Memory, memory_id).memory_content == "Draft fact."
        assert _row(other, GlossaryTerm, term_id).term == "Alpha"
        assert _row(other, TermTranslation, term_id).translation == "Alpha rendering"
        assert other.scalar(select(func.count()).select_from(GlossaryAssociation)) == 1
        assert other.scalar(select(func.count()).select_from(TranslationConvention)) == 1
        assert other.scalar(select(func.count()).select_from(Memory)) == 2
        assert other.get(MemoryWorkspace, workspace_id) is not None
    discard_workspace(test_db, workspace_id)
    test_db.commit()
    assert test_db.get(MemoryWorkspace, workspace_id) is None
    assert test_db.get(Memory, memory_id) is not None


def test_publication_copies_every_shadow_column_over_existing_rows(
    test_db: Session, reads: ReadScenario, publication_token: UUID
):
    _draft(test_db, reads)
    create_term_translation(test_db, reads.current, "Alpha", "Draft rendering")
    create_convention(
        test_db,
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
            for row in test_db.scalars(select(shadow).where(shadow.workspace_id == reads.workspace_id))
        ]
        assert len(payloads) == 1
        expected[model] = payloads
        test_db.execute(insert(model), payloads)
        test_db.execute(update(model).values(updated_at=datetime(2099, 1, 1)))
    test_db.commit()

    _publish(test_db, reads, publication_token)
    with Session(bind=test_db.get_bind()) as other:
        for model, _shadow in tables:
            actual = [dict(row) for row in other.execute(select(*inspect(model).columns)).mappings()]
            assert actual == expected[model]


def test_staged_memory_overwrites_content_and_review_changed_after_staging(
    test_db: Session,
    reads: ReadScenario,
    publication_token: UUID,
):
    access.create_term(test_db, reads.published.memory_group_id, "Alpha")
    original, _ = access.create_memory(
        test_db, reads.predecessor, Creator.AGENT, MemoryType.FACT, ["Alpha"], "Original."
    )
    access.expire_memory(test_db, reads.current, original.memory_id, [MemoryType.FACT])
    original.memory_content = "Human correction."
    original.memory_review_status = ReviewStatus.APPROVED
    test_db.commit()
    _publish(test_db, reads, publication_token)
    test_db.refresh(original)
    assert original.memory_end_num == 2
    assert original.memory_content == "Original." and original.memory_review_status == ReviewStatus.PENDING


def test_supersession_publishes_final_ids_and_convention_tombstones(
    test_db: Session,
    reads: ReadScenario,
    publication_token: UUID,
):
    access.create_term(test_db, reads.published.memory_group_id, "Alpha")
    original, _ = access.create_memory(
        test_db, reads.predecessor, Creator.AGENT, MemoryType.DEFINITION, ["Alpha"], "Old definition."
    )
    replacement, _ = access.supersede_memory(
        test_db, reads.current, original.memory_id, Creator.AGENT, MemoryType.DEFINITION, "New definition."
    )
    replacement_id = replacement.memory_id
    convention = create_convention(
        test_db,
        reads.published.memory_group_id,
        category=ConventionCategory.NAMING,
        title="Old guidance",
        rule="Withdraw this.",
        rationale=None,
        creator_type=Creator.AGENT,
    )
    convention_id = convention.convention_id
    delete_convention(
        test_db,
        reads.current.memory_group_id,
        convention_id,
        workspace_id=reads.workspace_id,
        only_creator=Creator.AGENT,
        only_pending=True,
    )
    convention.review_status = ReviewStatus.APPROVED
    test_db.commit()
    _publish(test_db, reads, publication_token)
    published = _row(test_db, Memory, replacement_id)
    assert published.supersedes_memory_id == original.memory_id
    test_db.refresh(original)
    assert original.memory_end_num == 2 and published.memory_start_num == 2
    assert test_db.get(TranslationConvention, convention_id) is None
    page = access.inspect_terms(test_db, reads.published, ["Alpha"], [MemoryType.DEFINITION])
    assert [row.memory.memory_id for row in page.rows] == [replacement_id]


def test_late_term_collision_rolls_back_every_published_change(
    test_db: Session,
    reads: ReadScenario,
    publication_token: UUID,
):
    _draft(test_db, reads)
    create_convention(
        test_db,
        reads.current.memory_group_id,
        workspace_id=reads.workspace_id,
        category=ConventionCategory.NAMING,
        title="Names",
        rule="Preserve forms.",
        rationale=None,
        creator_type=Creator.AGENT,
    )
    access.create_term(test_db, reads.published.memory_group_id, "Alpha")
    test_db.commit()
    with pytest.raises(IntegrityError):
        _publish(test_db, reads, publication_token)
    test_db.rollback()
    assert test_db.scalar(select(func.count()).select_from(Memory)) == 0
    assert test_db.scalar(select(func.count()).select_from(TranslationConvention)) == 0
    assert test_db.get(MemoryWorkspace, reads.workspace_id) is not None


def test_missing_association_parent_rolls_back_new_memories(
    test_db: Session,
    reads: ReadScenario,
    publication_token: UUID,
):
    term = access.create_term(test_db, reads.published.memory_group_id, "Alpha")
    access.create_memory(test_db, reads.current, Creator.AGENT, MemoryType.FACT, ["Alpha"], "Draft fact.")
    test_db.execute(delete(GlossaryTerm).where(GlossaryTerm.term_id == term.term_id))
    test_db.commit()
    with pytest.raises(IntegrityError):
        _publish(test_db, reads, publication_token)
    test_db.rollback()
    assert test_db.scalar(select(func.count()).select_from(Memory)) == 0


def test_staged_translations_and_summaries_overwrite_late_reviews(
    test_db: Session,
    reads: ReadScenario,
    publication_token: UUID,
):
    term = access.create_term(test_db, reads.published.memory_group_id, "Alpha")
    mapping = TermTranslation(
        term_id=term.term_id, translation="Rejected", review_status=ReviewStatus.REJECTED, creator_type=Creator.USER
    )
    test_db.add(mapping)
    test_db.flush()
    create_term_translation(test_db, reads.current, "Alpha", "Draft rendering")
    write_continuity_summary(test_db, reads.published, "Original handoff.")
    write_continuity_summary(test_db, reads.current, "Draft handoff.")
    summary = test_db.scalars(select(Memory).where(Memory.plugin_name == "continuity")).one()
    summary.memory_review_status = ReviewStatus.APPROVED
    mapping.translation, mapping.review_status = "Approved rendering", ReviewStatus.APPROVED
    test_db.commit()
    _publish(test_db, reads, publication_token)
    test_db.refresh(mapping)
    test_db.refresh(summary)
    assert mapping.translation == "Draft rendering" and mapping.review_status == ReviewStatus.PENDING
    assert summary.memory_content == "Draft handoff." and summary.memory_review_status == ReviewStatus.PENDING


def test_staged_conventions_overwrite_late_reviews(test_db: Session, reads: ReadScenario, publication_token: UUID):
    convention = create_convention(
        test_db,
        reads.published.memory_group_id,
        category=ConventionCategory.NAMING,
        title="Names",
        rule="Original.",
        rationale=None,
        creator_type=Creator.AGENT,
    )
    update_convention(
        test_db,
        reads.current.memory_group_id,
        convention.convention_id,
        workspace_id=reads.workspace_id,
        category=ConventionCategory.NAMING,
        title="Names",
        rule="Draft.",
        rationale=None,
        only_pending=True,
        only_creator=Creator.AGENT,
    )
    convention.review_status = ReviewStatus.APPROVED
    test_db.commit()
    _publish(test_db, reads, publication_token)
    test_db.refresh(convention)
    assert convention.rule == "Draft." and convention.review_status == ReviewStatus.PENDING


def test_unrelated_database_exception_is_not_reported_as_lost_claim(
    test_db: Session, reads: ReadScenario, publication_token: UUID
):
    term_id, _ = _draft(test_db, reads)
    test_db.commit()
    table = GlossaryTerm.__tablename__
    test_db.execute(
        text(
            "CREATE FUNCTION reject_publication() RETURNS trigger LANGUAGE plpgsql AS "
            "$$ BEGIN RAISE EXCEPTION 'unrelated failure'; END $$"
        )
    )
    test_db.execute(
        text(f'CREATE TRIGGER reject_publication BEFORE INSERT ON "{table}" EXECUTE FUNCTION reject_publication()')
    )
    test_db.commit()
    try:
        with pytest.raises(DBAPIError) as raised:
            _publish(test_db, reads, publication_token)
    finally:
        test_db.rollback()
        test_db.execute(text("DROP FUNCTION reject_publication() CASCADE"))
        test_db.commit()
    assert getattr(raised.value.orig, "pgcode", None) == "P0001"
    assert test_db.get(GlossaryTerm, term_id) is None


@pytest.mark.parametrize("claim_lost", ["expired", "replaced"])
def test_lost_claim_cannot_publish_committed_drafts(
    test_db: Session, reads: ReadScenario, testing_session_local: sessionmaker[Session], claim_lost: str
):
    task, token, result = _claimed(test_db, reads)
    term_id, memory_id = _draft(test_db, reads)
    test_db.commit()
    values = (
        {"claim_token": uuid4()}
        if claim_lost == "replaced"
        else {"claim_expires_at": func.now() - timedelta(seconds=1)}
    )
    test_db.execute(update(MemoryJob).where(MemoryJob.memory_job_id == task.memory_job_id).values(**values))
    test_db.commit()
    test_db.rollback()
    with pytest.raises(MemoryJobClaimLostException):
        tasks._complete_workspace_task(test_db, task, result, token, testing_session_local)
    assert test_db.get(Memory, memory_id) is None and test_db.get(GlossaryTerm, term_id) is None
    assert (
        _row(test_db, MemoryChapterTask, (task.memory_job_id, task.chapter_id, task.stage_num)).task_status
        == JobStatus.PROCESSING
    )


def test_cleanup_failure_leaves_completed_publication_and_safe_leftovers(
    test_db: Session, reads: ReadScenario, testing_session_local: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
):
    task, token, result = _claimed(test_db, reads)
    term_id, memory_id = _draft(test_db, reads)
    test_db.commit()

    def fail_cleanup(_db, _workspace_id):
        raise RuntimeError("cleanup unavailable")

    monkeypatch.setattr(tasks, "discard_workspace", fail_cleanup)
    tasks._complete_workspace_task(test_db, task, result, token, testing_session_local)
    assert test_db.get(Memory, memory_id) is not None and test_db.get(GlossaryTerm, term_id) is not None
    assert (
        _row(test_db, MemoryChapterTask, (task.memory_job_id, task.chapter_id, task.stage_num)).task_status
        == JobStatus.COMPLETED
    )
    assert test_db.get(MemoryWorkspace, reads.workspace_id) is not None
    test_db.rollback()
    with pytest.raises(MemoryJobClaimLostException):
        tasks._complete_workspace_task(test_db, task, result, token, testing_session_local)
    assert test_db.scalar(select(func.count()).select_from(Memory)) == 1


def test_lost_commit_acknowledgement_uses_persisted_task_state(
    test_db: Session, reads: ReadScenario, testing_session_local: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
):
    task, token, result = _claimed(test_db, reads)
    term_id, memory_id = _draft(test_db, reads)
    test_db.commit()
    engine = test_db.get_bind().engine
    lost = False

    def lose_ack(_conn, _cursor, statement, _params, _context, _many):
        nonlocal lost
        if statement.startswith("/* workspace:complete */") and not lost:
            lost = True
            raise ConnectionError("commit acknowledgement lost")

    event.listen(engine, "after_cursor_execute", lose_ack)
    try:
        tasks._complete_workspace_task(test_db, task, result, token, testing_session_local)
    finally:
        event.remove(engine, "after_cursor_execute", lose_ack)
    assert lost
    assert test_db.get(Memory, memory_id) is not None and test_db.get(GlossaryTerm, term_id) is not None
    assert test_db.get(MemoryWorkspace, reads.workspace_id) is None
    assert test_db.scalar(select(func.count()).select_from(Memory)) == 1
