from uuid import uuid4

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from src.memory.models import Memory, MemoryGroup
from src.memory.types import Creator, MemoryType, ReviewStatus
from src.novels.models import Chapter, ChapterContent
from src.translations.actions.common.memory_inputs import iter_batch_memories
from src.translations.models import TranslationBatch
from src.translations.schemas import TranslationJobCreate
from src.translations.tasks.jobs import create_job
from test_support.test_data.scenarios import DatabaseScenario


def test_batch_candidates_respect_boundaries_filters_and_use_one_query(
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    # Preparation needs stable chapter-local indices and all chapters, even when
    # no candidates match. SQL and database streaming remain real in this test.
    novel = sample_scenario.novels["novel_1"]
    chapter = sample_scenario.chapters["chapter_1"]
    chapter.chapter_num = 10
    second = Chapter(novel_id=novel.novel_id, chapter_num=11, chapter_title="Next", chapter_is_public=False)
    test_db.add(second)
    test_db.flush()
    test_db.add(
        ChapterContent(chapter_id=second.chapter_id, chapter_content_version=1, chapter_content_text="Next text")
    )
    group = MemoryGroup(novel_id=novel.novel_id, memory_group_name="Candidates", memory_language=novel.language_code)
    foreign_group = MemoryGroup(
        novel_id=sample_scenario.novels["novel_2"].novel_id,
        memory_group_name="Other novel",
        memory_language=novel.language_code,
    )
    test_db.add_all([group, foreign_group])
    test_db.flush()
    candidates = [
        ("prior", 9, None, ReviewStatus.PENDING, "continuity", group),
        ("same", 10, None, ReviewStatus.APPROVED, "glossary", group),
        ("expired", 8, 10, ReviewStatus.APPROVED, "continuity", group),
        ("future", 12, None, ReviewStatus.APPROVED, "continuity", group),
        ("rejected", 9, None, ReviewStatus.REJECTED, "continuity", group),
        ("foreign", 9, None, ReviewStatus.APPROVED, "continuity", foreign_group),
    ]
    for name, start, end, review, plugin, owner in candidates:
        test_db.add(
            Memory(
                memory_group_id=owner.memory_group_id,
                memory_observed_in=sample_scenario.contents["chapter_1_v2"].chapter_content_id,
                memory_type=MemoryType.FACT,
                memory_content=name,
                memory_start_num=start,
                memory_end_num=end,
                memory_review_status=review,
                creator_type=Creator.USER,
                plugin_name=plugin,
            )
        )
    test_db.commit()
    job_id = create_job(
        test_db,
        TranslationJobCreate.model_validate(
            {
                "novel_id": novel.novel_id,
                "config": {"batch_size": 10},
                "stages": [{"action": "prune_memories"}],
            }
        ),
    )
    batch_id = test_db.scalars(select(TranslationBatch.batch_id).where(TranslationBatch.job_id == job_id)).one()
    group_id = group.memory_group_id
    chapter_ids = [chapter.chapter_id, second.chapter_id]
    statements: list[str] = []

    def record_query(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    connection = test_db.connection()
    event.listen(connection, "before_cursor_execute", record_query)
    try:
        records = list(iter_batch_memories(test_db, job_id=job_id, batch_id=batch_id, memory_group_id=group_id))
    finally:
        event.remove(connection, "before_cursor_execute", record_query)
    assert len(statements) == 1
    assert [record.chapter_id for record in records] == chapter_ids
    assert [[m.memory_content for m in record.payload] for record in records] == [["prior"], ["same", "prior"]]
    included = list(
        iter_batch_memories(
            test_db, job_id=job_id, batch_id=batch_id, memory_group_id=group_id, exclude_current_chapter=False
        )
    )
    assert [m.memory_content for m in included[0].payload] == ["same", "prior"]
    filtered = list(
        iter_batch_memories(
            test_db,
            job_id=job_id,
            batch_id=batch_id,
            memory_group_id=group_id,
            plugin_names=["glossary"],
            memory_types=[MemoryType.FACT],
        )
    )
    assert [[m.memory_content for m in r.payload] for r in filtered] == [[], ["same"]]
    empty = list(
        iter_batch_memories(test_db, job_id=job_id, batch_id=batch_id, memory_group_id=group_id, memory_types=[])
    )
    assert len(empty) == 2 and all(not r.payload for r in empty)
    assert list(iter_batch_memories(test_db, job_id=job_id, batch_id=uuid4(), memory_group_id=group_id)) == []

    foreign = list(
        iter_batch_memories(test_db, job_id=job_id, batch_id=batch_id, memory_group_id=foreign_group.memory_group_id)
    )
    assert len(foreign) == 2 and all(not r.payload for r in foreign)
