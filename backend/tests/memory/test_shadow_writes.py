from dataclasses import replace
from uuid import uuid4

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.memory.access import expire_memory, write_continuity_summary
from src.memory.agent.capabilities.conventions import ConventionsOutput, write_conventions_output
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.glossary import common
from src.memory.agent.toolsets.glossary.terms import add_term
from src.memory.exceptions import (
    ConventionNotFoundException,
    GlossaryTermAlreadyExistsException,
    MemoryNotFoundException,
    MemoryWorkspaceNotFoundException,
)
from src.memory.models import Memory, MemoryGroup
from src.memory.plugins.conventions.access import (
    create_convention,
    delete_convention,
    read_conventions,
    update_convention,
)
from src.memory.plugins.conventions.models import TranslationConvention
from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.plugins.glossary import access
from src.memory.plugins.glossary.models import GlossaryAssociation, GlossaryTerm
from src.memory.plugins.glossary.types import TermKind
from src.memory.plugins.translations.access import create_term_translation, read_term_translations
from src.memory.plugins.translations.models import TermTranslation
from src.memory.shadow_models import (
    ShadowConvention,
    ShadowGlossaryAssociation,
    ShadowMemory,
    ShadowTerm,
    ShadowTermTranslation,
)
from src.memory.types import Creator, MemoryType, ReviewStatus, Scope
from tests.fixtures.memory_workspaces import ReadScenario
from tests.fixtures.memory_workspaces import reads as reads


def test_staged_term_memory_and_associations_survive_commit_without_publication(test_db: Session, reads: ReadScenario):
    term = access.create_term(
        test_db, reads.current.memory_group_id, "Alpha", TermKind.PERSON, workspace_id=reads.current.workspace_id
    )
    memory, associations = access.create_memory(
        test_db,
        reads.current,
        Creator.AGENT,
        MemoryType.FACT,
        ["Alpha", "Alpha"],
        "Draft fact.",
        Scope.PERSIST,
        "trait",
    )
    assert isinstance(term, ShadowTerm) and isinstance(memory, ShadowMemory)
    assert [(row.term_id, row.memory_id) for row in associations] == [(term.term_id, memory.memory_id)]
    memory_id, term_id = memory.memory_id, term.term_id
    test_db.commit()
    with Session(bind=test_db.get_bind()) as fresh:
        assert fresh.get(Memory, memory_id) is None
        assert fresh.get(GlossaryTerm, term_id) is None
        assert fresh.scalar(select(func.count()).select_from(GlossaryAssociation)) == 0
        assert access.get_terms_in_chapter(fresh, reads.published, access.contains_query) == []
        assert access.get_terms_in_chapter(fresh, reads.other, access.contains_query) == []
        page = access.inspect_terms(fresh, reads.current, ["Alpha"], [MemoryType.FACT])
        assert [(row.memory.memory_id, row.memory.memory_content) for row in page.rows] == [(memory_id, "Draft fact.")]
        assert page.rows[0].terms[0].term == "Alpha"


def test_term_uniqueness_checks_both_published_and_current_workspace(test_db: Session, reads: ReadScenario):
    access.create_term(test_db, reads.published.memory_group_id, "Alpha")
    with pytest.raises(GlossaryTermAlreadyExistsException):
        access.create_term(test_db, reads.current.memory_group_id, "Alpha", workspace_id=reads.current.workspace_id)
    ctx = RunContext(deps=MemAgentDeps(test_db, reads.current), model=TestModel(), usage=RunUsage())
    assert add_term(ctx, "【Beta】", TermKind.PERSON) == "Term Beta added successfully."
    with pytest.raises(ModelRetry, match="already exists"):
        add_term(ctx, "Beta", TermKind.PERSON)
    other = access.create_term(test_db, reads.other.memory_group_id, "Beta", workspace_id=reads.other.workspace_id)
    current = access.get_terms_in_chapter(test_db, reads.current, access.contains_query)
    assert other.term_id != next(row.term_id for row in current if row.term == "Beta")
    assert test_db.scalar(select(func.count()).select_from(GlossaryTerm)) == 1


@pytest.mark.parametrize("replace_terms", [False, True])
def test_supersession_copies_old_row_and_uses_visible_associations(
    test_db: Session, reads: ReadScenario, replace_terms: bool
):
    access.create_term(test_db, reads.published.memory_group_id, "Alpha")
    original, _ = access.create_memory(
        test_db, reads.predecessor, Creator.AGENT, MemoryType.FACT, ["Alpha"], "Published fact.", mark="trait"
    )
    if replace_terms:
        access.create_term(test_db, reads.current.memory_group_id, "Zeta", workspace_id=reads.current.workspace_id)
    replacement, associations = access.supersede_memory(
        test_db,
        reads.current,
        original.memory_id,
        Creator.AGENT,
        MemoryType.FACT,
        "Corrected fact.",
        mark="trait",
        replacement_term_names=["Zeta"] if replace_terms else None,
        expected_marks=["trait"],
    )
    assert isinstance(replacement, ShadowMemory)
    assert replacement.supersedes_memory_id == original.memory_id
    staged_original = test_db.get(ShadowMemory, (reads.current.workspace_id, original.memory_id))
    assert staged_original is not None and staged_original.memory_end_num == 2
    assert staged_original.created_at == original.created_at
    assert original.memory_end_num is None
    name = "Zeta" if replace_terms else "Alpha"
    page = access.inspect_terms(test_db, reads.current, [name], [MemoryType.FACT])
    assert [row.memory.memory_id for row in page.rows] == [replacement.memory_id]
    assert len(associations) == 1
    with pytest.raises(MemoryNotFoundException):
        access.supersede_memory(
            test_db,
            reads.current,
            original.memory_id,
            Creator.AGENT,
            MemoryType.FACT,
            "Already ended.",
            expected_marks=["trait"],
        )


def test_expiry_stages_existing_and_new_rows_without_changing_published_data(test_db: Session, reads: ReadScenario):
    access.create_term(test_db, reads.published.memory_group_id, "Alpha")
    original, _ = access.create_memory(
        test_db, reads.predecessor, Creator.AGENT, MemoryType.FACT, ["Alpha"], "Published fact.", mark="trait"
    )
    expire_memory(test_db, reads.current, original.memory_id)
    assert access.inspect_terms(test_db, reads.current, ["Alpha"], None).count == 0
    assert access.inspect_terms(test_db, reads.published, ["Alpha"], None).count == 1
    assert original.memory_end_num is None
    new, _ = access.create_memory(
        test_db,
        reads.current,
        Creator.AGENT,
        MemoryType.EVENT,
        ["Alpha"],
        "Draft event.",
        Scope.PERSIST,
        "gender.event.transformation",
    )
    with pytest.raises(MemoryNotFoundException):
        access.expire_memory(
            test_db,
            reads.current,
            new.memory_id,
            [MemoryType.FACT],
            marks=["gender.event.transformation"],
            end_offset=1,
        )
    access.expire_memory(
        test_db, reads.current, new.memory_id, [MemoryType.EVENT], marks=["gender.event.transformation"], end_offset=1
    )
    test_db.refresh(new)
    assert new.memory_end_num == 3
    assert test_db.get(Memory, new.memory_id) is None


def test_failed_supersession_rolls_back_shadow_copies_and_replacement(test_db: Session, reads: ReadScenario):
    access.create_term(test_db, reads.published.memory_group_id, "Alpha")
    original, _ = access.create_memory(
        test_db, reads.predecessor, Creator.AGENT, MemoryType.FACT, ["Alpha"], "Published fact.", mark="trait"
    )
    ctx = RunContext(deps=MemAgentDeps(test_db, reads.current), model=TestModel(), usage=RunUsage())
    handle = ctx.deps.memory_handles.new(original.memory_id)
    with pytest.raises(ModelRetry, match="Missing replacement glossary terms"):
        common.supersede_memory(
            ctx, handle, "Replacement.", MemoryType.FACT, Scope.PERSIST, "trait", ["Missing"], expected_marks=["trait"]
        )
    assert test_db.scalar(select(func.count()).select_from(ShadowMemory)) == 0
    assert test_db.scalar(select(func.count()).select_from(ShadowGlossaryAssociation)) == 0
    assert access.inspect_terms(test_db, reads.current, ["Alpha"], None).rows[0].memory.memory_end_num is None
    assert original.memory_end_num is None


@pytest.mark.parametrize("status", list(ReviewStatus))
def test_translation_staging_preserves_usable_choices_and_replaces_rejected_ones(
    test_db: Session, reads: ReadScenario, status: ReviewStatus
):
    alpha = access.create_term(test_db, reads.published.memory_group_id, "Alpha")
    published = TermTranslation(
        term_id=alpha.term_id, translation="Published", review_status=status, creator_type=Creator.USER
    )
    test_db.add(published)
    test_db.flush()
    create_term_translation(test_db, reads.current, "Alpha", "  Draft  ")
    if status == ReviewStatus.REJECTED:
        staged = test_db.get(ShadowTermTranslation, (reads.current.workspace_id, alpha.term_id))
        assert staged is not None and staged.translation == "Draft" and staged.creator_type == Creator.AGENT
        assert staged.review_status == ReviewStatus.PENDING
    else:
        assert test_db.get(ShadowTermTranslation, (reads.current.workspace_id, alpha.term_id)) is None
    assert published.translation == "Published" and published.review_status == status
    beta = access.create_term(test_db, reads.current.memory_group_id, "Beta", workspace_id=reads.current.workspace_id)
    create_term_translation(test_db, reads.current, "Beta", "New name")
    create_term_translation(test_db, reads.current, "Beta", "Must not replace pending")
    assert read_term_translations(test_db, reads.current, ["Beta"])[0].translation == "New name"
    assert test_db.get(TermTranslation, beta.term_id) is None
    with pytest.raises(ValueError, match="blank"):
        create_term_translation(test_db, reads.current, "Beta", "  ")


def test_convention_updates_and_deletions_use_drafts_and_tombstones(test_db: Session, reads: ReadScenario):
    original = create_convention(
        test_db,
        reads.published.memory_group_id,
        category=ConventionCategory.NAMING,
        title="Published",
        rule="Original rule.",
        rationale=None,
        creator_type=Creator.AGENT,
    )
    new = create_convention(
        test_db,
        reads.current.memory_group_id,
        category=ConventionCategory.NAMING,
        title="New",
        rule="New rule.",
        rationale=None,
        creator_type=Creator.AGENT,
        workspace_id=reads.current.workspace_id,
    )
    for row in (original, new):
        update_convention(
            test_db,
            reads.current.memory_group_id,
            row.convention_id,
            category=ConventionCategory.STYLE,
            title="Changed",
            rule="Changed rule.",
            rationale=None,
            only_creator=Creator.AGENT,
            only_pending=True,
            workspace_id=reads.current.workspace_id,
        )
    assert original.title == "Published"
    assert [
        row.rule
        for row in read_conventions(test_db, reads.current.memory_group_id, workspace_id=reads.current.workspace_id)
    ] == ["Changed rule."] * 2
    delete_convention(
        test_db, reads.current.memory_group_id, new.convention_id, workspace_id=reads.current.workspace_id
    )
    assert test_db.get(ShadowConvention, (reads.current.workspace_id, new.convention_id)) is None
    delete_convention(
        test_db,
        reads.current.memory_group_id,
        original.convention_id,
        workspace_id=reads.current.workspace_id,
        only_creator=Creator.AGENT,
        only_pending=True,
    )
    tombstone = test_db.get(ShadowConvention, (reads.current.workspace_id, original.convention_id))
    assert tombstone is not None and tombstone.deleted
    assert read_conventions(test_db, reads.current.memory_group_id, workspace_id=reads.current.workspace_id) == []
    assert test_db.get(TranslationConvention, original.convention_id) is original
    with pytest.raises(ConventionNotFoundException):
        delete_convention(
            test_db, reads.current.memory_group_id, original.convention_id, workspace_id=reads.current.workspace_id
        )


def test_convention_output_retries_roll_back_all_staged_changes(test_db: Session, reads: ReadScenario):
    locked = create_convention(
        test_db,
        reads.published.memory_group_id,
        category=ConventionCategory.NAMING,
        title="Reviewed",
        rule="Keep this.",
        rationale=None,
        creator_type=Creator.USER,
    )
    ctx = RunContext(deps=MemAgentDeps(test_db, reads.current), model=TestModel(), usage=RunUsage())
    handle = ctx.deps.convention_handles.new(locked.convention_id)
    test_db.commit()
    output = ConventionsOutput.model_validate(
        {
            "create": [{"category": "naming", "title": "Draft", "rule": "Draft rule."}],
            "revise": [{"handle": handle, "category": "naming", "title": "Revised", "rule": "Revised rule."}],
        }
    )
    with pytest.raises(ModelRetry, match="Nothing from this attempt was saved"):
        write_conventions_output(ctx, output)
    assert test_db.scalar(select(func.count()).select_from(ShadowConvention)) == 0
    assert locked.rule == "Keep this."
    write_conventions_output(ctx, ConventionsOutput(create=output.create))
    assert [
        row.title
        for row in read_conventions(test_db, reads.current.memory_group_id, workspace_id=reads.current.workspace_id)
    ] == ["Reviewed", "Draft"]
    assert test_db.scalar(select(func.count()).select_from(TranslationConvention)) == 1


@pytest.mark.parametrize(
    ("creator", "status"),
    [
        (Creator.AGENT, ReviewStatus.PENDING),
        (Creator.AGENT, ReviewStatus.APPROVED),
        (Creator.AGENT, ReviewStatus.REJECTED),
        (Creator.USER, ReviewStatus.PENDING),
    ],
)
def test_continuity_stages_only_updates_allowed_by_existing_policy(
    test_db: Session, reads: ReadScenario, creator: Creator, status: ReviewStatus
):
    write_continuity_summary(test_db, reads.published, "Published handoff.")
    original = test_db.scalars(select(Memory).where(Memory.plugin_name == "continuity")).one()
    original.creator_type, original.memory_review_status = creator, status
    test_db.flush()
    write_continuity_summary(test_db, reads.current, "Draft handoff.")
    write_continuity_summary(test_db, reads.current, "Latest draft handoff.")
    drafts = list(test_db.scalars(select(ShadowMemory)))
    if creator == Creator.AGENT and status == ReviewStatus.PENDING:
        assert len(drafts) == 1
        assert drafts[0].memory_id == original.memory_id
        assert drafts[0].memory_content == "Latest draft handoff."
    else:
        assert drafts == []
    assert original.memory_content == "Published handoff."


def test_new_continuity_summary_keeps_its_identity_when_rewritten(test_db: Session, reads: ReadScenario):
    write_continuity_summary(test_db, reads.current, "First handoff.")
    draft = test_db.scalars(select(ShadowMemory)).one()
    summary_id = draft.memory_id
    write_continuity_summary(test_db, reads.current, "Revised handoff.")
    test_db.refresh(draft)
    assert draft.memory_id == summary_id and draft.memory_content == "Revised handoff."
    assert test_db.scalar(select(func.count()).select_from(ShadowMemory)) == 1
    assert test_db.scalar(select(func.count()).select_from(Memory)) == 0


def test_writes_reject_workspaces_from_another_group_chapter_or_missing_workspace(
    test_db: Session, reads: ReadScenario
):
    group = test_db.get(MemoryGroup, reads.published.memory_group_id)
    assert group is not None
    other_group = MemoryGroup(novel_id=group.novel_id, memory_group_name="Other", memory_language=group.memory_language)
    test_db.add(other_group)
    test_db.flush()
    with pytest.raises(MemoryWorkspaceNotFoundException):
        access.create_term(test_db, other_group.memory_group_id, "Alpha", workspace_id=reads.current.workspace_id)
    with pytest.raises(MemoryWorkspaceNotFoundException):
        access.create_term(test_db, group.memory_group_id, "Alpha", workspace_id=uuid4())
    with pytest.raises(MemoryWorkspaceNotFoundException):
        write_continuity_summary(
            test_db, replace(reads.predecessor, workspace_id=reads.current.workspace_id), "Wrong chapter."
        )
    assert test_db.scalar(select(func.count()).select_from(ShadowTerm)) == 0
    assert test_db.scalar(select(func.count()).select_from(ShadowMemory)) == 0
