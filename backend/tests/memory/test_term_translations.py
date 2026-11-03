import pytest
from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.memory.access import MemAccessContext
from src.memory.agent.toolsets.translations.tools import term_translation_context
from src.memory.models import MemoryGroup
from src.memory.plugins.glossary import access
from src.memory.plugins.glossary.models import GlossaryTerm
from src.memory.plugins.translations.access import create_term_translation, read_term_translations
from src.memory.plugins.translations.models import TermTranslation
from src.memory.types import Creator, MemoryType, ReviewStatus
from src.novels.models import Chapter, ChapterContent
from test_support.test_data.scenarios import DatabaseScenario


def test_naming_context_reuses_alias_renderings_without_treating_them_as_exact_mappings(
    test_db: Session, sample_scenario: DatabaseScenario
):
    source = sample_scenario.contents["chapter_1_v2"]
    source.chapter_content_text = "Alpha meets Rejected."
    group = MemoryGroup(
        novel_id=sample_scenario.novels["novel_1"].novel_id, memory_group_name="Naming", memory_language="en"
    )
    test_db.add(group)
    test_db.flush()
    alpha = access.create_term(test_db, group.memory_group_id, "Alpha")
    beta = access.create_term(test_db, group.memory_group_id, "Beta")
    rejected = access.create_term(test_db, group.memory_group_id, "Rejected")
    rejected.review_status = ReviewStatus.REJECTED
    ctx = MemAccessContext(group.memory_group_id, source.chapter_id, source.chapter_content_id)
    access.create_memory(
        test_db,
        ctx,
        Creator.AGENT,
        MemoryType.RELATION,
        ["Alpha", "Beta"],
        "Alpha and Beta identify the same person.",
        mark="alias.persona",
    )
    test_db.add(TermTranslation(term_id=beta.term_id, translation="Existing Persona", creator_type=Creator.USER))
    test_db.flush()
    context = term_translation_context(test_db, ctx)
    assert context is not None
    assert [(term.term, term.kind) for term in context.requested_terms] == [("Alpha", None)]
    assert [mapping.model_dump(mode="json") for mapping in context.established_translations] == [
        {"term": "Beta", "translation": "Existing Persona", "review_status": "pending"}
    ]
    assert read_term_translations(test_db, ctx, ["Alpha"]) == []
    create_term_translation(test_db, ctx, "Alpha", "Alpha Rendering")
    approved = test_db.get(TermTranslation, alpha.term_id)
    assert approved is not None
    approved.translation, approved.review_status, approved.creator_type = (
        "Approved Alpha",
        ReviewStatus.APPROVED,
        Creator.USER,
    )
    test_db.flush()
    create_term_translation(test_db, ctx, "Alpha", "Must not overwrite")
    test_db.expire_all()
    assert test_db.scalar(select(func.count()).select_from(TermTranslation)) == 2
    assert read_term_translations(test_db, ctx, ["Alpha"])[0].translation == "Approved Alpha"
    assert term_translation_context(test_db, ctx) is None


def test_canonical_mapping_is_unique_shared_across_chapters_and_deleted_with_its_term(
    test_db: Session, sample_scenario: DatabaseScenario
):
    """Naming and preparation share a current mapping independent of chapter scope."""
    source = sample_scenario.contents["chapter_1_v2"]
    group = MemoryGroup(
        novel_id=sample_scenario.novels["novel_1"].novel_id, memory_group_name="Shared naming", memory_language="en"
    )
    test_db.add(group)
    test_db.flush()
    term = access.create_term(test_db, group.memory_group_id, "Alpha")
    later = Chapter(novel_id=group.novel_id, chapter_num=999, chapter_title="Later", chapter_is_public=False)
    test_db.add(later)
    test_db.flush()
    later_source = ChapterContent(chapter_id=later.chapter_id, chapter_content_version=1, chapter_content_text="Alpha")
    test_db.add(later_source)
    test_db.flush()
    later_ctx = MemAccessContext(group.memory_group_id, later.chapter_id, later_source.chapter_content_id)
    earlier_ctx = MemAccessContext(group.memory_group_id, source.chapter_id, source.chapter_content_id)
    create_term_translation(test_db, later_ctx, "Alpha", "First rendering")
    create_term_translation(test_db, earlier_ctx, "Alpha", "Must not overwrite a pending choice")
    assert read_term_translations(test_db, earlier_ctx, ["Alpha"])[0].translation == "First rendering"
    with pytest.raises(IntegrityError), test_db.begin_nested():
        test_db.execute(
            insert(TermTranslation).values(term_id=term.term_id, translation="Duplicate", creator_type=Creator.AGENT)
        )
    test_db.execute(delete(GlossaryTerm).where(GlossaryTerm.term_id == term.term_id))
    test_db.expire_all()
    assert test_db.scalar(select(func.count()).select_from(TermTranslation)) == 0


def test_rejected_mappings_can_be_regenerated_and_rejected_source_terms_are_excluded(
    test_db: Session, sample_scenario: DatabaseScenario
):
    source = sample_scenario.contents["chapter_1_v2"]
    group = MemoryGroup(
        novel_id=sample_scenario.novels["novel_1"].novel_id, memory_group_name="Retry naming", memory_language="en"
    )
    test_db.add(group)
    test_db.flush()
    term = access.create_term(test_db, group.memory_group_id, "Alpha")
    ctx = MemAccessContext(group.memory_group_id, source.chapter_id, source.chapter_content_id)
    create_term_translation(test_db, ctx, "Alpha", "Rejected rendering")
    row = test_db.get(TermTranslation, term.term_id)
    assert row is not None
    row.review_status = ReviewStatus.REJECTED
    test_db.flush()
    assert read_term_translations(test_db, ctx, ["Alpha"]) == []
    create_term_translation(test_db, ctx, "Alpha", "Replacement")
    test_db.expire_all()
    mapping = read_term_translations(test_db, ctx, ["Alpha"])[0]
    assert mapping.translation == "Replacement" and mapping.review_status == ReviewStatus.PENDING
    assert test_db.scalar(select(func.count()).select_from(TermTranslation)) == 1
    term = test_db.get(GlossaryTerm, term.term_id)
    assert term is not None
    term.review_status = ReviewStatus.REJECTED
    test_db.flush()
    assert read_term_translations(test_db, ctx, ["Alpha"]) == []
