import json
import os
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai import capture_run_messages
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.usage import RunUsage
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.languages.models import Language
from src.memory.agent.agent import create_agent, run_novel
from src.memory.glossary.models import GlossaryAssociation, GlossaryTerm
from src.memory.models import Memory, MemoryGroup
from src.novels.models import SourceWork
from test_support.test_data import load_catalog, load_novel
from test_support.test_data.materializer import make_novel, materialize_novel_contents

REPO_ROOT = Path(__file__).resolve().parents[3]
SNAKE_CATALOG_ROOT = REPO_ROOT / "tmp" / "snake-catalog"
RUNS_ROOT = REPO_ROOT / "tmp" / "runs" / "snake"

pytestmark = [
    pytest.mark.agent,
    pytest.mark.slow,
    pytest.mark.skipif(not SNAKE_CATALOG_ROOT.is_dir(), reason=f"private catalog not found at {SNAKE_CATALOG_ROOT}"),
    pytest.mark.skipif(not os.getenv("DEEPSEEK_API_KEY"), reason="DEEPSEEK_API_KEY is not exported"),
]


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _serialize_usage(usage: RunUsage) -> dict[str, Any]:
    return {
        "requests": usage.requests,
        "toolCalls": usage.tool_calls,
        "inputTokens": usage.input_tokens,
        "outputTokens": usage.output_tokens,
        "cacheWriteTokens": usage.cache_write_tokens,
        "cacheReadTokens": usage.cache_read_tokens,
        "totalTokens": usage.total_tokens,
        "costUsd": str(usage.cost) if usage.cost is not None else None,
        "details": usage.details,
    }


def _serialize_exception(exc: BaseException) -> dict[str, object]:
    serialized: dict[str, object] = {
        "type": type(exc).__name__,
        "message": str(exc),
    }
    errors = getattr(exc, "errors", None)
    if callable(errors):
        try:
            validation_errors = errors(include_input=True)
        except TypeError:
            validation_errors = errors()
        serialized["errors"] = json.loads(json.dumps(validation_errors, ensure_ascii=False, default=str))
    return serialized


def _serialize_failure(exc: BaseException, chapter_num: int | None = None) -> dict[str, object]:
    failure = _serialize_exception(exc)
    if chapter_num is not None:
        failure["chapterNum"] = chapter_num

    causes: list[dict[str, object]] = []
    seen = {id(exc)}
    cause = exc.__cause__ if exc.__cause__ is not None else exc.__context__
    while cause is not None and id(cause) not in seen:
        seen.add(id(cause))
        causes.append(_serialize_exception(cause))
        cause = cause.__cause__ if cause.__cause__ is not None else cause.__context__
    if causes:
        failure["causes"] = causes
    return failure


def _snapshot_memory(db: Session, memory_group_id: uuid.UUID) -> dict[str, object]:
    terms = db.scalars(
        select(GlossaryTerm)
        .where(GlossaryTerm.memory_group_id == memory_group_id)
        .order_by(GlossaryTerm.term, GlossaryTerm.term_id)
    ).all()
    memories = db.scalars(
        select(Memory)
        .where(Memory.memory_group_id == memory_group_id)
        .order_by(Memory.memory_start_num, Memory.created_at, Memory.memory_id)
    ).all()
    associations = db.scalars(
        select(GlossaryAssociation)
        .join(Memory, Memory.memory_id == GlossaryAssociation.memory_id)
        .where(Memory.memory_group_id == memory_group_id)
        .order_by(GlossaryAssociation.term_id, GlossaryAssociation.memory_id)
    ).all()

    return {
        "terms": [
            {
                "termId": str(term.term_id),
                "term": term.term,
                "reviewStatus": term.review_status.value,
                "createdAt": term.created_at.isoformat(),
                "updatedAt": term.updated_at.isoformat(),
            }
            for term in terms
        ],
        "memories": [
            {
                "memoryId": str(memory.memory_id),
                "memoryType": memory.memory_type.value,
                "observedIn": str(memory.memory_observed_in),
                "startNum": memory.memory_start_num,
                "endNum": memory.memory_end_num,
                "supersedesMemoryId": (
                    str(memory.supersedes_memory_id) if memory.supersedes_memory_id is not None else None
                ),
                "content": memory.memory_content,
                "reviewStatus": memory.memory_review_status.value,
                "creatorType": memory.creator_type.value,
                "createdAt": memory.created_at.isoformat(),
                "updatedAt": memory.updated_at.isoformat(),
            }
            for memory in memories
        ],
        "associations": [
            {"termId": str(association.term_id), "memoryId": str(association.memory_id)}
            for association in associations
        ],
    }


async def test_run_snake_chapters_1_through_50(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    catalog = load_catalog(SNAKE_CATALOG_ROOT)
    complete_dataset = load_novel(catalog, "private-snake")
    dataset = replace(complete_dataset, chapters=complete_dataset.chapters[:50])
    assert [chapter.number for chapter in dataset.chapters] == list(range(1, 51))

    chinese = Language(language_name="Chinese", language_code="zh")
    english = Language(language_name="English", language_code="en")
    source_work = SourceWork(source_work_title=dataset.title)
    test_db.add_all([chinese, english, source_work])
    test_db.flush()

    novel = make_novel(dataset, source_work)
    test_db.add(novel)
    test_db.flush()
    materialize_novel_contents(test_db, dataset, novel)

    memory_group = MemoryGroup(
        memory_group_name="Snake memory-agent run",
        novel_id=novel.novel_id,
        memory_language="en",
    )
    test_db.add(memory_group)
    test_db.commit()

    started_at = datetime.now(UTC)
    run_dir = RUNS_ROOT / started_at.strftime("%Y%m%dT%H%M%S.%fZ")
    chapters_dir = run_dir / "chapters"
    chapters_dir.mkdir(parents=True)

    completed_chapters: list[int] = []
    aggregate_usage = RunUsage()
    failure: dict[str, object] | None = None

    try:
        results = run_novel(
            testing_session_local,
            create_agent("deepseek:deepseek-chat", ["glossary"]),
            novel.novel_id,
            memory_group.memory_group_id,
            start_chapter_num=1,
            end_chapter_num=51,
        )
        result_iterator = aiter(results)
        while True:
            with capture_run_messages() as messages:
                try:
                    chapter_num, result = await anext(result_iterator)
                except StopAsyncIteration:
                    break
                except Exception as exc:
                    failed_chapter_num = completed_chapters[-1] + 1 if completed_chapters else 1
                    failure = _serialize_failure(exc, failed_chapter_num)
                    _write_json(
                        chapters_dir / f"chapter-{failed_chapter_num:04d}.failed.json",
                        {
                            "chapterNum": failed_chapter_num,
                            "timestamp": datetime.now(UTC).isoformat(),
                            "failure": failure,
                            "messages": json.loads(ModelMessagesTypeAdapter.dump_json(messages)),
                        },
                    )
                    raise
            aggregate_usage.incr(result.usage)
            completed_chapters.append(chapter_num)
            _write_json(
                chapters_dir / f"chapter-{chapter_num:04d}.json",
                {
                    "chapterNum": chapter_num,
                    "runId": result.run_id,
                    "timestamp": result.timestamp.isoformat(),
                    "output": result.output,
                    "usage": _serialize_usage(result.usage),
                    "messages": json.loads(result.all_messages_json()),
                },
            )
    except Exception as exc:
        if failure is None:
            failure = _serialize_failure(exc)
        raise
    finally:
        finished_at = datetime.now(UTC)
        with testing_session_local() as snapshot_db:
            _write_json(run_dir / "memory.json", _snapshot_memory(snapshot_db, memory_group.memory_group_id))
        _write_json(
            run_dir / "metadata.json",
            {
                "status": "failed" if failure is not None else "completed",
                "startedAt": started_at.isoformat(),
                "finishedAt": finished_at.isoformat(),
                "model": "deepseek:deepseek-chat",
                "plugins": ["glossary"],
                "catalog": "tmp/snake-catalog",
                "novel": "private-snake",
                "chapterRange": {"startInclusive": 1, "endExclusive": 51},
                "completedChapters": completed_chapters,
                "usage": _serialize_usage(aggregate_usage),
                "failure": failure,
            },
        )

    assert completed_chapters == list(range(1, 51))
