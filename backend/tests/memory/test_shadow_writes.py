from dataclasses import replace
from uuid import uuid4

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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


async def test_staged_term_memory_and_associations_survive_commit_without_publication(
    async_test_db: AsyncSession, reads: ReadScenario
):
    term = await access.create_term(
        async_test_db, reads.current.memory_group_id, "Alpha", TermKind.PERSON, workspace_id=reads.current.workspace_id
    )
    memory, associations = await access.create_memory(
        async_test_db,
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
    await async_test_db.commit()
    async with AsyncSession(async_test_db.bind) as fresh:
        assert await fresh.get(Memory, memory_id) is None
        assert await fresh.get(GlossaryTerm, term_id) is None
        assert await fresh.scalar(select(func.count()).select_from(GlossaryAssociation)) == 0
        assert await access.get_terms_in_chapter(fresh, reads.published, access.contains_query) == []
        assert await access.get_terms_in_chapter(fresh, reads.other, access.contains_query) == []
        page = await access.inspect_terms(fresh, reads.current, ["Alpha"], [MemoryType.FACT])
        assert [(row.memory.memory_id, row.memory.memory_content) for row in page.rows] == [(memory_id, "Draft fact.")]
        assert page.rows[0].terms[0].term == "Alpha"


async def test_term_uniqueness_checks_both_published_and_current_workspace(
    async_test_db: AsyncSession, reads: ReadScenario
):
    await access.create_term(async_test_db, reads.published.memory_group_id, "Alpha")
    with pytest.raises(GlossaryTermAlreadyExistsException):
        await access.create_term(
            async_test_db, reads.current.memory_group_id, "Alpha", workspace_id=reads.current.workspace_id
        )
    ctx = RunContext(deps=MemAgentDeps(async_test_db, reads.current), model=TestModel(), usage=RunUsage())
    assert await add_term(ctx, "【Beta】", TermKind.PERSON) == "Term Beta added successfully."
    with pytest.raises(ModelRetry, match="already exists"):
        await add_term(ctx, "Beta", TermKind.PERSON)
    other = await access.create_term(
        async_test_db, reads.other.memory_group_id, "Beta", workspace_id=reads.other.workspace_id
    )
    current = await access.get_terms_in_chapter(async_test_db, reads.current, access.contains_query)
    assert other.term_id != next(row.term_id for row in current if row.term == "Beta")
    assert await async_test_db.scalar(select(func.count()).select_from(GlossaryTerm)) == 1


@pytest.mark.parametrize("replace_terms", [False, True])
async def test_supersession_copies_old_row_and_uses_visible_associations(
    async_test_db: AsyncSession, reads: ReadScenario, replace_terms: bool
):
    await access.create_term(async_test_db, reads.published.memory_group_id, "Alpha")
    original, _ = await access.create_memory(
        async_test_db, reads.predecessor, Creator.AGENT, MemoryType.FACT, ["Alpha"], "Published fact.", mark="trait"
    )
    if replace_terms:
        await access.create_term(
            async_test_db, reads.current.memory_group_id, "Zeta", workspace_id=reads.current.workspace_id
        )
    replacement, associations = await access.supersede_memory(
        async_test_db,
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
    staged_original = await async_test_db.get(ShadowMemory, (reads.current.workspace_id, original.memory_id))
    assert staged_original is not None and staged_original.memory_end_num == 2
    assert staged_original.created_at == original.created_at
    assert original.memory_end_num is None
    name = "Zeta" if replace_terms else "Alpha"
    page = await access.inspect_terms(async_test_db, reads.current, [name], [MemoryType.FACT])
    assert [row.memory.memory_id for row in page.rows] == [replacement.memory_id]
    assert len(associations) == 1
    with pytest.raises(MemoryNotFoundException):
        await access.supersede_memory(
            async_test_db,
            reads.current,
            original.memory_id,
            Creator.AGENT,
            MemoryType.FACT,
            "Already ended.",
            expected_marks=["trait"],
        )


async def test_expiry_stages_existing_and_new_rows_without_changing_published_data(
    async_test_db: AsyncSession, reads: ReadScenario
):
    await access.create_term(async_test_db, reads.published.memory_group_id, "Alpha")
    original, _ = await access.create_memory(
        async_test_db, reads.predecessor, Creator.AGENT, MemoryType.FACT, ["Alpha"], "Published fact.", mark="trait"
    )
    await expire_memory(async_test_db, reads.current, original.memory_id)
    assert (await access.inspect_terms(async_test_db, reads.current, ["Alpha"], None)).count == 0
    assert (await access.inspect_terms(async_test_db, reads.published, ["Alpha"], None)).count == 1
    assert original.memory_end_num is None
    new, _ = await access.create_memory(
        async_test_db,
        reads.current,
        Creator.AGENT,
        MemoryType.EVENT,
        ["Alpha"],
        "Draft event.",
        Scope.PERSIST,
        "gender.event.transformation",
    )
    with pytest.raises(MemoryNotFoundException):
        await access.expire_memory(
            async_test_db,
            reads.current,
            new.memory_id,
            [MemoryType.FACT],
            marks=["gender.event.transformation"],
            end_offset=1,
        )
    await access.expire_memory(
        async_test_db,
        reads.current,
        new.memory_id,
        [MemoryType.EVENT],
        marks=["gender.event.transformation"],
        end_offset=1,
    )
    await async_test_db.refresh(new)
    assert new.memory_end_num == 3
    assert await async_test_db.get(Memory, new.memory_id) is None


async def test_failed_supersession_rolls_back_shadow_copies_and_replacement(
    async_test_db: AsyncSession, reads: ReadScenario
):
    await access.create_term(async_test_db, reads.published.memory_group_id, "Alpha")
    original, _ = await access.create_memory(
        async_test_db, reads.predecessor, Creator.AGENT, MemoryType.FACT, ["Alpha"], "Published fact.", mark="trait"
    )
    ctx = RunContext(deps=MemAgentDeps(async_test_db, reads.current), model=TestModel(), usage=RunUsage())
    handle = ctx.deps.memory_handles.new(original.memory_id)
    with pytest.raises(ModelRetry, match="Missing replacement glossary terms"):
        await common.supersede_memory(
            ctx, handle, "Replacement.", MemoryType.FACT, Scope.PERSIST, "trait", ["Missing"], expected_marks=["trait"]
        )
    assert await async_test_db.scalar(select(func.count()).select_from(ShadowMemory)) == 0
    assert await async_test_db.scalar(select(func.count()).select_from(ShadowGlossaryAssociation)) == 0
    assert (await access.inspect_terms(async_test_db, reads.current, ["Alpha"], None)).rows[
        0
    ].memory.memory_end_num is None
    assert original.memory_end_num is None


@pytest.mark.parametrize("status", list(ReviewStatus))
async def test_translation_staging_preserves_usable_choices_and_replaces_rejected_ones(
    async_test_db: AsyncSession, reads: ReadScenario, status: ReviewStatus
):
    alpha = await access.create_term(async_test_db, reads.published.memory_group_id, "Alpha")
    published = TermTranslation(
        term_id=alpha.term_id, translation="Published", review_status=status, creator_type=Creator.USER
    )
    async_test_db.add(published)
    await async_test_db.flush()
    await create_term_translation(async_test_db, reads.current, "Alpha", "  Draft  ")
    if status == ReviewStatus.REJECTED:
        staged = await async_test_db.get(ShadowTermTranslation, (reads.current.workspace_id, alpha.term_id))
        assert staged is not None and staged.translation == "Draft" and staged.creator_type == Creator.AGENT
        assert staged.review_status == ReviewStatus.PENDING
    else:
        assert await async_test_db.get(ShadowTermTranslation, (reads.current.workspace_id, alpha.term_id)) is None
    assert published.translation == "Published" and published.review_status == status
    beta = await access.create_term(
        async_test_db, reads.current.memory_group_id, "Beta", workspace_id=reads.current.workspace_id
    )
    await create_term_translation(async_test_db, reads.current, "Beta", "New name")
    await create_term_translation(async_test_db, reads.current, "Beta", "Must not replace pending")
    assert (await read_term_translations(async_test_db, reads.current, ["Beta"]))[0].translation == "New name"
    assert await async_test_db.get(TermTranslation, beta.term_id) is None
    with pytest.raises(ValueError, match="blank"):
        await create_term_translation(async_test_db, reads.current, "Beta", "  ")


async def test_convention_updates_and_deletions_use_drafts_and_tombstones(
    async_test_db: AsyncSession, reads: ReadScenario
):
    original = await create_convention(
        async_test_db,
        reads.published.memory_group_id,
        category=ConventionCategory.NAMING,
        title="Published",
        rule="Original rule.",
        rationale=None,
        creator_type=Creator.AGENT,
    )
    new = await create_convention(
        async_test_db,
        reads.current.memory_group_id,
        category=ConventionCategory.NAMING,
        title="New",
        rule="New rule.",
        rationale=None,
        creator_type=Creator.AGENT,
        workspace_id=reads.current.workspace_id,
    )
    for row in (original, new):
        await update_convention(
            async_test_db,
            reads.current.memory_group_id,
            row.convention_id,
            category=ConventionCategory.STYLE,
            title="Changed",
            rule="Changed rule.",
            rationale=None,
            only_creator=Creator.AGENT,
            only_pending=True,
            workspace_id=reads.current.workspace_id,
            recorded_on=reads.current.chapter_content_id,
        )
    assert original.title == "Published"
    assert [
        row.rule
        for row in await read_conventions(
            async_test_db, reads.current.memory_group_id, workspace_id=reads.current.workspace_id
        )
    ] == ["Changed rule."] * 2
    await delete_convention(
        async_test_db, reads.current.memory_group_id, new.convention_id, workspace_id=reads.current.workspace_id
    )
    assert await async_test_db.get(ShadowConvention, (reads.current.workspace_id, new.convention_id)) is None
    await delete_convention(
        async_test_db,
        reads.current.memory_group_id,
        original.convention_id,
        workspace_id=reads.current.workspace_id,
        only_creator=Creator.AGENT,
        only_pending=True,
    )
    tombstone = await async_test_db.get(ShadowConvention, (reads.current.workspace_id, original.convention_id))
    assert tombstone is not None and tombstone.deleted
    assert (
        await read_conventions(async_test_db, reads.current.memory_group_id, workspace_id=reads.current.workspace_id)
        == []
    )
    assert await async_test_db.get(TranslationConvention, original.convention_id) is original
    with pytest.raises(ConventionNotFoundException):
        await delete_convention(
            async_test_db,
            reads.current.memory_group_id,
            original.convention_id,
            workspace_id=reads.current.workspace_id,
        )


async def test_convention_output_retries_roll_back_all_staged_changes(async_test_db: AsyncSession, reads: ReadScenario):
    locked = await create_convention(
        async_test_db,
        reads.published.memory_group_id,
        category=ConventionCategory.NAMING,
        title="Reviewed",
        rule="Keep this.",
        rationale=None,
        creator_type=Creator.USER,
    )
    ctx = RunContext(deps=MemAgentDeps(async_test_db, reads.current), model=TestModel(), usage=RunUsage())
    handle = ctx.deps.convention_handles.new(locked.convention_id)
    await async_test_db.commit()
    output = ConventionsOutput.model_validate(
        {
            "create": [{"category": "naming", "title": "Draft", "rule": "Draft rule."}],
            "revise": [{"handle": handle, "category": "naming", "title": "Revised", "rule": "Revised rule."}],
        }
    )
    with pytest.raises(ModelRetry, match="Nothing from this attempt was saved"):
        await write_conventions_output(ctx, output)
    assert await async_test_db.scalar(select(func.count()).select_from(ShadowConvention)) == 0
    await async_test_db.refresh(locked)
    assert locked.rule == "Keep this."
    await write_conventions_output(ctx, ConventionsOutput(create=output.create))
    assert [
        row.title
        for row in await read_conventions(
            async_test_db, reads.current.memory_group_id, workspace_id=reads.current.workspace_id
        )
    ] == ["Reviewed", "Draft"]
    assert await async_test_db.scalar(select(func.count()).select_from(TranslationConvention)) == 1


@pytest.mark.parametrize(
    ("creator", "status"),
    [
        (Creator.AGENT, ReviewStatus.PENDING),
        (Creator.AGENT, ReviewStatus.APPROVED),
        (Creator.AGENT, ReviewStatus.REJECTED),
        (Creator.USER, ReviewStatus.PENDING),
    ],
)
async def test_continuity_stages_only_updates_allowed_by_existing_policy(
    async_test_db: AsyncSession, reads: ReadScenario, creator: Creator, status: ReviewStatus
):
    await write_continuity_summary(async_test_db, reads.published, "Published handoff.")
    original = (await async_test_db.scalars(select(Memory).where(Memory.plugin_name == "continuity"))).one()
    original.creator_type, original.memory_review_status = creator, status
    await async_test_db.flush()
    await write_continuity_summary(async_test_db, reads.current, "Draft handoff.")
    await write_continuity_summary(async_test_db, reads.current, "Latest draft handoff.")
    drafts = list(await async_test_db.scalars(select(ShadowMemory)))
    if creator == Creator.AGENT and status == ReviewStatus.PENDING:
        assert len(drafts) == 1
        assert drafts[0].memory_id == original.memory_id
        assert drafts[0].memory_content == "Latest draft handoff."
    else:
        assert drafts == []
    assert original.memory_content == "Published handoff."


async def test_new_continuity_summary_keeps_its_identity_when_rewritten(
    async_test_db: AsyncSession, reads: ReadScenario
):
    await write_continuity_summary(async_test_db, reads.current, "First handoff.")
    draft = (await async_test_db.scalars(select(ShadowMemory))).one()
    summary_id = draft.memory_id
    await write_continuity_summary(async_test_db, reads.current, "Revised handoff.")
    await async_test_db.refresh(draft)
    assert draft.memory_id == summary_id and draft.memory_content == "Revised handoff."
    assert await async_test_db.scalar(select(func.count()).select_from(ShadowMemory)) == 1
    assert await async_test_db.scalar(select(func.count()).select_from(Memory)) == 0


async def test_writes_reject_workspaces_from_another_group_chapter_or_missing_workspace(
    async_test_db: AsyncSession, reads: ReadScenario
):
    group = await async_test_db.get(MemoryGroup, reads.published.memory_group_id)
    assert group is not None
    other_group = MemoryGroup(novel_id=group.novel_id, memory_group_name="Other", memory_language=group.memory_language)
    async_test_db.add(other_group)
    await async_test_db.flush()
    with pytest.raises(MemoryWorkspaceNotFoundException):
        await access.create_term(
            async_test_db, other_group.memory_group_id, "Alpha", workspace_id=reads.current.workspace_id
        )
    with pytest.raises(MemoryWorkspaceNotFoundException):
        await access.create_term(async_test_db, group.memory_group_id, "Alpha", workspace_id=uuid4())
    with pytest.raises(MemoryWorkspaceNotFoundException):
        await write_continuity_summary(
            async_test_db, replace(reads.predecessor, workspace_id=reads.current.workspace_id), "Wrong chapter."
        )
    assert await async_test_db.scalar(select(func.count()).select_from(ShadowTerm)) == 0
    assert await async_test_db.scalar(select(func.count()).select_from(ShadowMemory)) == 0
