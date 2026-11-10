from typing import Any

from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from src.memory.access import MemAccessContext, read_previous_continuity_summary, write_continuity_summary
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.conventions.context import conventions_context
from src.memory.agent.toolsets.conventions.tools import search_glossary_terms
from src.memory.agent.toolsets.translations.tools import term_translation_context
from src.memory.models import Memory
from src.memory.plugins.conventions.access import create_convention, read_conventions
from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.plugins.glossary import access
from src.memory.plugins.glossary.models import GlossaryTerm
from src.memory.plugins.glossary.schemas import AgentGlossaryMemoryPage
from src.memory.plugins.glossary.types import TermKind
from src.memory.plugins.translations.access import missing_term_translations, read_term_translations
from src.memory.plugins.translations.models import TermTranslation
from src.memory.shadow_models import (
    ShadowConvention,
    ShadowGlossaryAssociation,
    ShadowMemory,
    ShadowTerm,
    ShadowTermTranslation,
)
from src.memory.types import Creator, MemoryType, ReviewStatus, Scope
from src.models import Base
from tests.fixtures.memory_workspaces import ReadScenario
from tests.fixtures.memory_workspaces import reads as reads


def _stage[T: Base](db: Session, model: type[T], ctx: MemAccessContext, original: Base, **changes: Any) -> T:
    payload = {column.name: getattr(original, column.name) for column in inspect(type(original)).columns}
    payload.update(changes)
    row = model(workspace_id=ctx.workspace_id, **payload)
    db.add(row)
    db.flush()
    return row


def _draft_term(db: Session, ctx: MemAccessContext, name: str) -> ShadowTerm:
    row = ShadowTerm(workspace_id=ctx.workspace_id, memory_group_id=ctx.memory_group_id, term=name)
    db.add(row)
    db.flush()
    return row


def _draft_memory(
    db: Session,
    ctx: MemAccessContext,
    term: GlossaryTerm | ShadowTerm,
    content: str,
    *,
    kind: MemoryType = MemoryType.FACT,
    mark: str | None = None,
) -> ShadowMemory:
    row = ShadowMemory(
        workspace_id=ctx.workspace_id,
        memory_group_id=ctx.memory_group_id,
        memory_type=kind,
        memory_observed_in=ctx.chapter_content_id,
        memory_start_num=2,
        memory_content=content,
        creator_type=Creator.AGENT,
        plugin_name="glossary",
        mark=mark,
    )
    db.add(row)
    db.flush()
    db.add(ShadowGlossaryAssociation(workspace_id=ctx.workspace_id, term_id=term.term_id, memory_id=row.memory_id))
    db.flush()
    return row


def test_term_overlays_isolate_cached_published_rows_and_refresh_drafts(test_db: Session, reads: ReadScenario):
    alpha = access.create_term(test_db, reads.published.memory_group_id, "Alpha", TermKind.PERSON)
    beta = access.create_term(test_db, reads.published.memory_group_id, "Beta")
    staged = _stage(test_db, ShadowTerm, reads.current, alpha, term="Gamma")
    _stage(test_db, ShadowTerm, reads.current, beta, deleted=True)
    _draft_term(test_db, reads.current, "Zeta")

    def names(ctx: MemAccessContext) -> list[str]:
        return [row.term for row in access.get_terms_in_chapter(test_db, ctx, access.contains_query)]

    assert names(reads.published) == names(reads.other) == ["Alpha", "Beta"]
    assert names(reads.current) == ["Gamma", "Zeta"]
    assert (alpha.term, beta.term) == ("Alpha", "Beta")
    assert access.search_terms(
        test_db, reads.current.memory_group_id, "Alpha", limit=10, workspace_id=reads.current.workspace_id
    ) == (0, [])
    assert access.get_missing_term_names(
        test_db,
        reads.current.memory_group_id,
        ["Alpha", "Gamma", "Beta", "Zeta"],
        workspace_id=reads.current.workspace_id,
    ) == ["Alpha", "Beta"]
    staged.term = "Delta"
    test_db.flush()
    assert names(reads.current) == ["Delta", "Zeta"]
    assert names(reads.published) == ["Alpha", "Beta"]
    staged.review_status = ReviewStatus.REJECTED
    test_db.flush()
    assert names(reads.current) == ["Zeta"]
    rows, truncated = access.get_terms_in_chapter_range(test_db, reads.current, 1, limit=1, include_rejected=True)
    assert [(row.term.term, row.first_chapter_num) for row in rows] == [("Delta", 1)]
    assert truncated


def test_memory_filters_counts_and_pages_apply_after_overrides(test_db: Session, reads: ReadScenario):
    alpha = access.create_term(test_db, reads.published.memory_group_id, "Alpha")
    originals = [
        access.create_memory(test_db, reads.published, Creator.AGENT, MemoryType.FACT, ["Alpha"], text)[0]
        for text in ["Changed type", "Deleted", "Ended", "Rejected"]
    ]
    _stage(test_db, ShadowMemory, reads.current, originals[0], memory_type=MemoryType.EVENT)
    _stage(test_db, ShadowMemory, reads.current, originals[1], deleted=True)
    _stage(test_db, ShadowMemory, reads.current, originals[2], memory_start_num=1, memory_end_num=2)
    _stage(test_db, ShadowMemory, reads.current, originals[3], memory_review_status=ReviewStatus.REJECTED)
    first = _draft_memory(test_db, reads.current, alpha, "Draft first")
    second = _draft_memory(test_db, reads.current, alpha, "Draft second")
    expected_ids = sorted([first.memory_id, second.memory_id])
    for skip in range(2):
        page = access.inspect_terms(test_db, reads.current, ["Alpha"], [MemoryType.FACT], skip=skip, limit=1)
        assert page.count == 2
        assert [item.memory.memory_id for item in page.rows] == expected_ids[skip : skip + 1]
    assert access.inspect_terms(test_db, reads.published, ["Alpha"], [MemoryType.FACT]).count == 4
    assert access.inspect_terms(test_db, reads.other, ["Alpha"], [MemoryType.FACT]).count == 4
    assert access.inspect_terms(test_db, reads.current, ["Alpha"], [MemoryType.FACT], term_search="second").count == 1
    assert access.inspect_terms(test_db, reads.current, ["Alpha"], [MemoryType.FACT], active_only=False).count == 3
    assert access.inspect_terms(test_db, reads.current, ["Alpha"], [MemoryType.FACT], include_rejected=True).count == 3


def test_association_overlays_match_both_key_columns_and_unpublished_endpoints(test_db: Session, reads: ReadScenario):
    alpha = access.create_term(test_db, reads.published.memory_group_id, "Alpha")
    access.create_term(test_db, reads.published.memory_group_id, "Beta")
    memory, associations = access.create_memory(
        test_db, reads.published, Creator.AGENT, MemoryType.FACT, ["Alpha", "Beta"], "Shared fact"
    )
    alpha_association = next(row for row in associations if row.term_id == alpha.term_id)
    _stage(test_db, ShadowGlossaryAssociation, reads.current, alpha_association, deleted=True)
    gamma = _draft_term(test_db, reads.current, "Gamma")
    test_db.add(
        ShadowGlossaryAssociation(
            workspace_id=reads.current.workspace_id, term_id=gamma.term_id, memory_id=memory.memory_id
        )
    )
    test_db.flush()
    assert access.inspect_terms(test_db, reads.current, ["Alpha"], None).count == 0
    page = access.inspect_terms(test_db, reads.current, ["Beta", "Gamma"], None)
    assert page.count == 1
    assert [row.term for row in page.rows[0].terms] == ["Beta", "Gamma"]
    assert access.inspect_terms(test_db, reads.published, ["Alpha"], None).count == 1


def test_alias_expansion_uses_shadow_terms_memories_and_associations(test_db: Session, reads: ReadScenario):
    alpha = access.create_term(test_db, reads.published.memory_group_id, "Alpha")
    beta = _draft_term(test_db, reads.current, "Beta")
    alias = _draft_memory(
        test_db, reads.current, alpha, "Alpha is also Beta.", kind=MemoryType.RELATION, mark=access.ALIAS_PERSONA_MARK
    )
    test_db.add(
        ShadowGlossaryAssociation(
            workspace_id=reads.current.workspace_id, term_id=beta.term_id, memory_id=alias.memory_id
        )
    )
    definition = _draft_memory(test_db, reads.current, beta, "Beta definition.", kind=MemoryType.DEFINITION)
    page = access.inspect_terms(test_db, reads.current, ["Alpha"], [MemoryType.DEFINITION], expand_aliases=True)
    assert isinstance(page, AgentGlossaryMemoryPage)
    assert [item.memory.memory_id for item in page.rows] == [definition.memory_id]
    assert [[term.term for term in item.terms] for item in page.aliases] == [["Alpha", "Beta"]]
    alias.deleted = True
    test_db.flush()
    assert (
        access.inspect_terms(test_db, reads.current, ["Alpha"], [MemoryType.DEFINITION], expand_aliases=True).count == 0
    )


def test_translation_overlays_mask_rejected_deleted_and_renamed_rows(test_db: Session, reads: ReadScenario):
    alpha = access.create_term(test_db, reads.published.memory_group_id, "Alpha")
    published = TermTranslation(term_id=alpha.term_id, translation="Published", creator_type=Creator.USER)
    test_db.add(published)
    test_db.flush()
    staged = _stage(test_db, ShadowTermTranslation, reads.current, published, translation="Draft")
    beta = _draft_term(test_db, reads.current, "Beta")
    test_db.add(
        ShadowTermTranslation(
            workspace_id=reads.current.workspace_id,
            term_id=beta.term_id,
            translation="New name",
            creator_type=Creator.AGENT,
        )
    )
    test_db.flush()
    assert [
        (row.term, row.translation) for row in read_term_translations(test_db, reads.current, ["Alpha", "Beta"])
    ] == [("Alpha", "Draft"), ("Beta", "New name")]
    assert [(row.term, row.translation) for row in read_term_translations(test_db, reads.other, ["Alpha", "Beta"])] == [
        ("Alpha", "Published")
    ]
    staged.review_status = ReviewStatus.REJECTED
    test_db.flush()
    assert missing_term_translations(test_db, reads.current, ["Alpha", "Beta", "Alpha"]) == ["Alpha"]
    staged.review_status = ReviewStatus.PENDING
    staged.deleted = True
    test_db.flush()
    assert read_term_translations(test_db, reads.current, ["Alpha"]) == []
    staged.deleted = False
    _stage(test_db, ShadowTerm, reads.current, alpha, term="Gamma")
    assert read_term_translations(test_db, reads.current, ["Alpha"]) == []
    assert read_term_translations(test_db, reads.current, ["Gamma"])[0].translation == "Draft"
    assert published.translation == "Published"


def test_convention_filters_and_agent_contexts_read_the_workspace(test_db: Session, reads: ReadScenario):
    alpha = _draft_term(test_db, reads.current, "Alpha")
    _draft_memory(test_db, reads.current, alpha, "A staged definition.", kind=MemoryType.DEFINITION)
    originals = [
        create_convention(
            test_db,
            reads.published.memory_group_id,
            category=ConventionCategory.NAMING,
            title=title,
            rule="Published rule.",
            rationale=None,
            creator_type=Creator.AGENT,
        )
        for title in ["Changed category", "Deleted"]
    ]
    _stage(test_db, ShadowConvention, reads.current, originals[0], category=ConventionCategory.STYLE)
    _stage(test_db, ShadowConvention, reads.current, originals[1], deleted=True)
    draft = ShadowConvention(
        workspace_id=reads.current.workspace_id,
        memory_group_id=reads.current.memory_group_id,
        category=ConventionCategory.NAMING,
        title="Draft policy",
        rule="Draft rule.",
        creator_type=Creator.AGENT,
    )
    test_db.add(draft)
    test_db.flush()
    assert [
        row.title
        for row in read_conventions(
            test_db,
            reads.current.memory_group_id,
            workspace_id=reads.current.workspace_id,
            category=ConventionCategory.NAMING,
        )
    ] == ["Draft policy"]
    assert len(read_conventions(test_db, reads.published.memory_group_id, category=ConventionCategory.NAMING)) == 2
    naming = term_translation_context(test_db, reads.current, include_conventions=True)
    assert naming is not None and [term.term for term in naming.requested_terms] == ["Alpha"]
    assert naming.conventions is not None and [row.title for row in naming.conventions] == ["Draft policy"]
    context = conventions_context(MemAgentDeps(test_db, reads.current), 1)
    assert [term.definition for term in context.terms] == ["A staged definition."]
    assert {row.title for row in context.conventions} == {"Changed category", "Draft policy"}
    search = search_glossary_terms(
        RunContext(deps=MemAgentDeps(test_db, reads.current), model=TestModel(), usage=RunUsage()), "Alpha"
    )
    assert search.count == 1 and [row.term for row in search.terms] == ["Alpha"]
    draft.review_status = ReviewStatus.REJECTED
    test_db.flush()
    assert (
        read_conventions(
            test_db,
            reads.current.memory_group_id,
            workspace_id=reads.current.workspace_id,
            category=ConventionCategory.NAMING,
            review_statuses=[ReviewStatus.PENDING],
        )
        == []
    )


def test_continuity_and_event_guards_use_shadow_visibility(test_db: Session, reads: ReadScenario):
    write_continuity_summary(test_db, reads.predecessor, "Published handoff.")
    summary = test_db.scalars(select(Memory).where(Memory.plugin_name == "continuity")).one()
    staged_summary = _stage(test_db, ShadowMemory, reads.current, summary, memory_content="Draft handoff.")
    assert read_previous_continuity_summary(test_db, reads.current) == "Draft handoff."
    assert read_previous_continuity_summary(test_db, reads.other) == "Published handoff."
    staged_summary.deleted = True
    test_db.flush()
    assert read_previous_continuity_summary(test_db, reads.current) is None

    access.create_term(test_db, reads.published.memory_group_id, "Alpha")
    event, _ = access.create_memory(
        test_db,
        reads.predecessor,
        Creator.AGENT,
        MemoryType.EVENT,
        ["Alpha"],
        "An occurrence.",
        Scope.PERSIST,
        "gender.event.transformation",
    )
    staged_event = _stage(test_db, ShadowMemory, reads.current, event, memory_end_num=2)
    chapter_num, history = access.read_agent_event_history(
        test_db, reads.current, "Alpha", "gender.event.transformation"
    )
    assert chapter_num == 2 and [row.memory_end_num for row in history] == [2]
    assert not access.can_supersede_agent_event(
        test_db, reads.current, event.memory_id, "Alpha", "gender.event.transformation"
    )
    assert access.can_supersede_agent_event(
        test_db, reads.other, event.memory_id, "Alpha", "gender.event.transformation"
    )
    staged_event.deleted = True
    test_db.flush()
    assert access.read_agent_event_history(test_db, reads.current, "Alpha", "gender.event.transformation") == (2, [])
