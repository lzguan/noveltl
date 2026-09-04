from pydantic_ai import FunctionToolset, RunContext, RunUsage
from pydantic_ai.models.test import TestModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.languages.models import Language
from src.memory.access import MemAccessContext, reject_memory
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.glossary.gender_advanced_events import (
    create_glossary_gender_advanced_events_write_toolset,
)
from src.memory.agent.types import OccurrenceRetentionConfig
from src.memory.models import Memory, MemoryGroup
from src.memory.plugins.glossary.access import (
    GLOSSARY_PLUGIN_NAME,
    create_memory,
    create_term,
)
from src.memory.plugins.glossary.models import GlossaryAssociation
from src.memory.plugins.glossary.types import TermKind
from src.memory.types import Creator, MemoryType, ReviewStatus, Scope
from src.novels.constants import NovelType, Visibility
from src.novels.models import Chapter, ChapterContent, Novel, SourceWork

TRANSFORMATION_MARK = "gender.event.transformation"


def test_transformation_retention_bounds_agent_occurrences_without_touching_other_records(
    test_db: Session,
) -> None:
    language = Language(language_name="Chinese", language_code="zh")
    source_work = SourceWork(source_work_title="Transformation retention source")
    test_db.add_all([language, source_work])
    test_db.flush()
    novel = Novel(
        novel_title="Transformation retention novel",
        novel_description=None,
        novel_author=None,
        novel_visibility=Visibility.PRIVATE,
        novel_type=NovelType.ORIGINAL,
        source_work_id=source_work.source_work_id,
        language_code=language.language_code,
    )
    test_db.add(novel)
    test_db.flush()

    chapters = [
        Chapter(
            chapter_num=number,
            chapter_title=f"Chapter {number}",
            chapter_is_public=False,
            novel_id=novel.novel_id,
        )
        for number in range(1, 9)
    ]
    test_db.add_all(chapters)
    test_db.flush()
    contents = [
        ChapterContent(
            chapter_content_text=f"Chapter {chapter.chapter_num}",
            chapter_content_version=1,
            chapter_id=chapter.chapter_id,
        )
        for chapter in chapters
    ]
    memory_group = MemoryGroup(
        memory_group_name="Transformation retention group",
        novel_id=novel.novel_id,
        memory_language=language.language_code,
    )
    test_db.add_all([*contents, memory_group])
    test_db.flush()
    alpha = create_term(test_db, memory_group.memory_group_id, "Alpha", TermKind.PERSON)
    beta = create_term(test_db, memory_group.memory_group_id, "Beta", TermKind.PERSON)
    create_term(test_db, memory_group.memory_group_id, "Gamma", TermKind.PERSON)
    create_term(test_db, memory_group.memory_group_id, "Delta", TermKind.PERSON)

    def context(chapter_number: int) -> MemAccessContext:
        chapter = chapters[chapter_number - 1]
        content = contents[chapter_number - 1]
        return MemAccessContext(
            memory_group_id=memory_group.memory_group_id,
            chapter_id=chapter.chapter_id,
            chapter_content_id=content.chapter_content_id,
        )

    deps = MemAgentDeps(db=test_db, mem_access_context=context(1))
    run_context = RunContext(deps=deps, model=TestModel(), usage=RunUsage())
    retained_toolset = create_glossary_gender_advanced_events_write_toolset(
        OccurrenceRetentionConfig(keep_first=2, keep_rolling=2)
    )
    keep_first_toolset = create_glossary_gender_advanced_events_write_toolset(
        OccurrenceRetentionConfig(keep_first=1, keep_rolling=0)
    )
    zero_retention_toolset = create_glossary_gender_advanced_events_write_toolset(
        OccurrenceRetentionConfig(keep_first=0, keep_rolling=0)
    )

    def create_transformation(
        toolset: FunctionToolset[MemAgentDeps],
        chapter_number: int,
        subject: str,
        content: str,
    ) -> Memory:
        deps.mem_access_context = context(chapter_number)
        handle = toolset.tools["new_gender_transformation_event_memory"].function(
            run_context,
            subject,
            content,
        )
        return test_db.scalars(
            select(Memory).where(Memory.memory_id == deps.uuid_cache.get_uuid(handle))
        ).one()

    def correct_transformation(
        chapter_number: int,
        memory: Memory,
        subject: str,
        content: str,
    ) -> Memory:
        deps.mem_access_context = context(chapter_number)
        handle = deps.uuid_cache.new(memory.memory_id)
        replacement_handle = retained_toolset.tools[
            "supersede_gender_transformation_event_memory"
        ].function(run_context, handle, subject, content)
        return test_db.scalars(
            select(Memory).where(Memory.memory_id == deps.uuid_cache.get_uuid(replacement_handle))
        ).one()

    human_memory, _ = create_memory(
        test_db,
        context(1),
        Creator.USER,
        MemoryType.EVENT,
        ["Alpha"],
        "A human-authored transformation record.",
        Scope.PERSIST,
        TRANSFORMATION_MARK,
    )
    beta_memory = create_transformation(
        retained_toolset,
        1,
        "Beta",
        "Beta transformation 1.",
    )
    rejected_first = create_transformation(
        keep_first_toolset,
        1,
        "Delta",
        "Rejected first Delta transformation.",
    )
    reject_memory(test_db, memory_group.memory_group_id, rejected_first.memory_id)
    first = create_transformation(
        retained_toolset,
        1,
        "Alpha",
        "Alpha transformation 1.",
    )
    replacement_first = create_transformation(
        keep_first_toolset,
        2,
        "Delta",
        "First accepted Delta transformation.",
    )
    second = create_transformation(
        retained_toolset,
        2,
        "Alpha",
        "Alpha transformation 2.",
    )
    rejected = create_transformation(
        retained_toolset,
        3,
        "Alpha",
        "Rejected transformation.",
    )
    reject_memory(test_db, memory_group.memory_group_id, rejected.memory_id)
    fourth = create_transformation(
        retained_toolset,
        4,
        "Alpha",
        "Alpha transformation 3.",
    )
    corrected_first = correct_transformation(
        5,
        first,
        "Alpha",
        "Corrected Alpha transformation 1.",
    )
    fifth = create_transformation(
        retained_toolset,
        7,
        "Alpha",
        "Alpha transformation 4.",
    )
    sixth = create_transformation(
        retained_toolset,
        7,
        "Alpha",
        "Alpha transformation 5.",
    )
    unretained = create_transformation(
        zero_retention_toolset,
        7,
        "Gamma",
        "Gamma transformation 1.",
    )
    test_db.flush()

    active_alpha_agent_ids = set(
        test_db.scalars(
            select(Memory.memory_id)
            .join(GlossaryAssociation, GlossaryAssociation.memory_id == Memory.memory_id)
            .where(
                GlossaryAssociation.term_id == alpha.term_id,
                Memory.memory_group_id == memory_group.memory_group_id,
                Memory.plugin_name == GLOSSARY_PLUGIN_NAME,
                Memory.creator_type == Creator.AGENT,
                Memory.memory_type == MemoryType.EVENT,
                Memory.mark == TRANSFORMATION_MARK,
                Memory.memory_review_status != ReviewStatus.REJECTED,
                Memory.memory_start_num <= 8,
                or_(Memory.memory_end_num.is_(None), Memory.memory_end_num > 8),
            )
        ).all()
    )
    assert active_alpha_agent_ids == {
        corrected_first.memory_id,
        second.memory_id,
        fifth.memory_id,
        sixth.memory_id,
    }

    test_db.refresh(first)
    test_db.refresh(fourth)
    test_db.refresh(rejected)
    test_db.refresh(human_memory)
    test_db.refresh(beta_memory)
    test_db.refresh(unretained)
    test_db.refresh(replacement_first)
    assert first.memory_end_num == 5
    assert fourth.memory_end_num == 7
    assert rejected.memory_end_num is None
    assert human_memory.memory_end_num is None
    assert beta_memory.memory_end_num is None
    assert unretained.memory_end_num == 8
    assert replacement_first.memory_end_num is None
    assert beta_memory.plugin_name == GLOSSARY_PLUGIN_NAME
    assert (
        test_db.scalar(
            select(GlossaryAssociation).where(
                GlossaryAssociation.memory_id == beta_memory.memory_id,
                GlossaryAssociation.term_id == beta.term_id,
            )
        )
        is not None
    )
