"""Conventions stage with FunctionModel in place of inference; context, tools, and writes are real."""

import asyncio
import json

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.languages.models import Language
from src.memory.access import MemAccessContext
from src.memory.agent.agents import conventions as conventions_agent
from src.memory.agent.config import JobParamsV3, SummarizeConventionsStageConfig
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.prompts.conventions import conventions_request_prompt
from src.memory.agent.stages.conventions import run_conventions_stage
from src.memory.agent.tasks import tasks as agent_tasks
from src.memory.agent.tasks.jobs import make_job
from src.memory.agent.toolsets.conventions.context import ConventionsContext
from src.memory.models import MemoryChapterTask, MemoryGroup
from src.memory.plugins.conventions.access import read_conventions
from src.memory.plugins.glossary import access as glossary
from src.memory.plugins.glossary.types import TermKind
from src.memory.plugins.term_search.access import TextOccurrences, count_text_occurrences
from src.memory.types import Creator, JobStatus, ReviewStatus
from src.novels.constants import NovelType, Visibility
from src.novels.models import Chapter, ChapterContent, Novel, SourceWork

MODEL = "deepseek:deepseek-v4-flash-low"
CHAPTER_TEXTS = {1: ["种级出现。"], 2: ["旧版卵级", "卵级与种级，种级。"], 3: ["蛹级在后面。"]}


def _setup(db: Session) -> tuple[Novel, MemoryGroup, dict[int, MemAccessContext]]:
    language = Language(language_name="Chinese", language_code="zh")
    source_work = SourceWork(source_work_title="Agent source")
    db.add_all([language, source_work])
    db.flush()
    novel = Novel(
        novel_title="Agent novel",
        novel_description=None,
        novel_author=None,
        novel_visibility=Visibility.PRIVATE,
        novel_type=NovelType.ORIGINAL,
        source_work_id=source_work.source_work_id,
        language_code=language.language_code,
    )
    db.add(novel)
    db.flush()
    group = MemoryGroup(memory_group_name="Agent", novel_id=novel.novel_id, memory_language=language.language_code)
    db.add(group)
    db.flush()
    contexts: dict[int, MemAccessContext] = {}
    for chapter_num, versions in CHAPTER_TEXTS.items():
        chapter = Chapter(
            chapter_num=chapter_num, chapter_title=f"Ch{chapter_num}", chapter_is_public=False, novel_id=novel.novel_id
        )
        db.add(chapter)
        db.flush()
        for version, text in enumerate(versions, start=1):
            content = ChapterContent(
                chapter_id=chapter.chapter_id, chapter_content_version=version, chapter_content_text=text
            )
            db.add(content)
            db.flush()
            contexts[chapter_num] = MemAccessContext(
                group.memory_group_id, chapter.chapter_id, content.chapter_content_id
            )
    for term in ["种级", "卵级"]:
        glossary.create_term(db, group.memory_group_id, term, TermKind.TITLE)
    db.commit()
    return novel, group, contexts


def test_text_occurrences_use_latest_content_up_to_the_context_chapter(test_db: Session) -> None:
    _, _, contexts = _setup(test_db)

    results = count_text_occurrences(test_db, contexts[2], ["种级", "卵级", "蛹级", "无", "种级"])

    assert results == [
        TextOccurrences("种级", first_chapter_num=1, chapter_count=2, match_count=3),
        TextOccurrences("卵级", first_chapter_num=2, chapter_count=1, match_count=1),
        # Chapter 3 is past the context's chapter; texts need not be glossary terms.
        TextOccurrences("蛹级", first_chapter_num=None, chapter_count=0, match_count=0),
        TextOccurrences("无", first_chapter_num=None, chapter_count=0, match_count=0),
    ]


def _fake_agent(monkeypatch: pytest.MonkeyPatch, seen: list) -> None:
    """Call term_occurrences once, then propose one convention."""

    def respond(messages, info: AgentInfo) -> ModelResponse:
        seen.append(messages)
        if len(seen) == 1:
            return ModelResponse(parts=[ToolCallPart("term_occurrences", {"texts": ["种级", "卵级"]})])
        output = {
            "create": [
                {"category": "naming", "title": "Rank ladder", "rule": "Render …级 as …-rank: 种级 → Seed-rank."}
            ]
        }
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, output)])

    monkeypatch.setattr(conventions_agent, "model_configuration", lambda _: (FunctionModel(respond), {}))


def test_stage_shows_the_range_calls_tools_and_writes_conventions(
    test_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, group, contexts = _setup(test_db)
    seen: list = []
    _fake_agent(monkeypatch, seen)
    deps = MemAgentDeps(db=test_db, mem_access_context=contexts[2])

    result = asyncio.run(run_conventions_stage(deps, 2, "English", SummarizeConventionsStageConfig(model_name=MODEL)))

    assert result is not None
    prompt = next(part for part in seen[0][0].parts if isinstance(part, UserPromptPart))
    assert "the first chapter through chapter 2, rendering into English" in str(prompt.content)
    context = json.loads(str(prompt.content).split("Context:\n", 1)[1])
    assert [term["term"] for term in context["terms"]] == ["种级", "卵级"]
    tool_return = next(
        part
        for message in seen[1]
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart) and part.tool_name == "term_occurrences"
    )
    assert [entry["term"] for entry in json.loads(tool_return.model_response_str())] == ["种级", "卵级"]
    [stored] = read_conventions(test_db, group.memory_group_id)
    assert (stored.title, stored.creator_type, stored.review_status) == (
        "Rank ladder",
        Creator.AGENT,
        ReviewStatus.PENDING,
    )


def test_stage_skips_the_model_when_no_terms_occur_in_the_range(
    test_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, contexts = _setup(test_db)
    seen: list = []
    _fake_agent(monkeypatch, seen)
    deps = MemAgentDeps(db=test_db, mem_access_context=contexts[3])

    config = SummarizeConventionsStageConfig(model_name=MODEL, since_chapter_num=3)
    assert asyncio.run(run_conventions_stage(deps, 3, "English", config)) is None
    assert seen == []


def test_conventions_job_commits_the_agent_output_with_its_task(
    test_db: Session, testing_session_local, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, group, _ = _setup(test_db)
    _fake_agent(monkeypatch, [])
    job_id = make_job(
        test_db,
        group.memory_group_id,
        None,
        None,
        JobParamsV3(stages=[SummarizeConventionsStageConfig(model_name=MODEL)]),
    )

    async def consume():
        return [item async for item in agent_tasks.run_all_tasks(testing_session_local, job_id)]

    [completed] = asyncio.run(consume())

    test_db.expire_all()
    [task] = test_db.scalars(select(MemoryChapterTask).where(MemoryChapterTask.memory_job_id == job_id)).all()
    assert task.task_status == JobStatus.COMPLETED and completed.stage_name == "summarize_conventions"
    assert [row.title for row in read_conventions(test_db, group.memory_group_id)] == ["Rank ladder"]


def test_request_prompt_states_an_explicit_start_including_zero() -> None:
    context = ConventionsContext(conventions=[], terms=[], terms_truncated=False)
    assert "chapters 0–5," in conventions_request_prompt(context, 5, 0, "English")
    assert "chapters 3–5," in conventions_request_prompt(context, 5, 3, "English")
