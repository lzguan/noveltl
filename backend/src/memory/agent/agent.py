import uuid
from collections.abc import AsyncIterator
from itertools import batched

from pydantic_ai import Agent, AgentRunResult, FunctionToolset
from pydantic_ai.models.openai import OpenAIChatModelSettings
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased, defer, sessionmaker

from src.languages.models import Language
from src.memory.access import MemAccessContext
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.prompts.prompt import MEMORY_AGENT_PROMPT
from src.memory.agent.toolsets.glossary_context import GLOSSARY_SHARED_INSTRUCTIONS, initial_glossary_context
from src.memory.agent.toolsets.glossary_definitions import glossary_definition_toolset
from src.memory.agent.toolsets.glossary_events import glossary_event_toolset
from src.memory.agent.toolsets.glossary_facts import glossary_fact_toolset
from src.memory.agent.toolsets.glossary_relations import glossary_relation_toolset
from src.memory.agent.toolsets.glossary_terms import glossary_term_toolset
from src.memory.agent.types import TOOLSET_NAMES, ModelName, ToolsetName
from src.memory.models import MemoryGroup
from src.novels.models import Chapter, ChapterContent

toolsets_by_name: dict[ToolsetName, FunctionToolset[MemAgentDeps]] = {
    "glossary_terms": glossary_term_toolset,
    "glossary_definitions": glossary_definition_toolset,
    "glossary_relations": glossary_relation_toolset,
    "glossary_facts": glossary_fact_toolset,
    "glossary_events": glossary_event_toolset,
}

if set(toolsets_by_name) != set(TOOLSET_NAMES):
    raise RuntimeError("Memory-agent toolset registry does not match TOOLSET_NAMES")

GLOSSARY_TOOLSET_NAMES: frozenset[ToolsetName] = frozenset(
    {
        "glossary_terms",
        "glossary_definitions",
        "glossary_relations",
        "glossary_facts",
        "glossary_events",
    }
)


def create_agent(model_name: ModelName, toolsets: list[ToolsetName]) -> Agent[MemAgentDeps, str]:
    """Create a Pydantic AI agent with the specified model and toolsets.

    The model name's suffix selects the reasoning level. DeepSeek V4 does not
    accept `reasoning_effort="none"` (it 400s); non-thinking mode is requested
    via its native `thinking: {"type": "disabled"}` body flag instead. So the
    "-none" variant passes that through `extra_body` and leaves `thinking`
    unset, rather than using pydantic-ai's `thinking=False` (which would map to
    the rejected `reasoning_effort="none"`).
    """
    if model_name == "deepseek:deepseek-v4-flash-none":
        model_settings: OpenAIChatModelSettings = {"extra_body": {"thinking": {"type": "disabled"}}}
    else:  # deepseek:deepseek-v4-flash-low
        model_settings = {"thinking": "low"}
    glossary_enabled = any(toolset in GLOSSARY_TOOLSET_NAMES for toolset in toolsets)
    instructions = (
        [MEMORY_AGENT_PROMPT, GLOSSARY_SHARED_INSTRUCTIONS, initial_glossary_context]
        if glossary_enabled
        else MEMORY_AGENT_PROMPT
    )
    return Agent(
        model="deepseek:deepseek-v4-flash",
        model_settings=model_settings,
        toolsets=[toolsets_by_name[toolset] for toolset in toolsets],
        instructions=instructions,
        deps_type=MemAgentDeps,
    )


async def run_agent(
    agent: Agent[MemAgentDeps, str],
    deps: MemAgentDeps,
    chapter_text: str,
    chapter_num: int,
    language_name: str,
) -> AgentRunResult[str]:
    """Run the agent with the given input text and dependencies."""

    prompt = f"Record memories with content written in {language_name} from the following chapter text (chapter {chapter_num}):\n\n{chapter_text}"
    return await agent.run(
        prompt,
        deps=deps,
    )


async def run_novel(
    db_factory: sessionmaker[Session],
    agent: Agent[MemAgentDeps, str],
    novel_id: uuid.UUID,
    memory_group_id: uuid.UUID,
    *,
    start_chapter_num: int | None = None,
    end_chapter_num: int | None = None,
) -> AsyncIterator[tuple[int, AgentRunResult[str]]]:
    """Run the agent over a half-open range of a novel's chapters."""
    if start_chapter_num is not None and start_chapter_num < 1:
        raise ValueError("start_chapter_num must be positive")
    if end_chapter_num is not None and end_chapter_num < 1:
        raise ValueError("end_chapter_num must be positive")
    if start_chapter_num is not None and end_chapter_num is not None and start_chapter_num > end_chapter_num:
        raise ValueError("start_chapter_num must not exceed end_chapter_num")

    latest_chapter_content = aliased(ChapterContent)
    with db_factory() as db:
        chapter_query = (
            select(Chapter, ChapterContent)
            .where(Chapter.novel_id == novel_id)
            .join(ChapterContent, ChapterContent.chapter_id == Chapter.chapter_id)
            .where(
                ChapterContent.chapter_content_version
                == select(latest_chapter_content.chapter_content_version)
                .where(latest_chapter_content.chapter_id == Chapter.chapter_id)
                .order_by(latest_chapter_content.chapter_content_version.desc())
                .limit(1)
                .scalar_subquery()
            )
            .options(defer(ChapterContent.chapter_content_text))
            .order_by(Chapter.chapter_num)
        )
        if start_chapter_num is not None:
            chapter_query = chapter_query.where(Chapter.chapter_num >= start_chapter_num)
        if end_chapter_num is not None:
            chapter_query = chapter_query.where(Chapter.chapter_num < end_chapter_num)
        chapters = db.execute(chapter_query).all()
        language_name = db.execute(
            select(Language.language_name)
            .select_from(MemoryGroup)
            .where(MemoryGroup.memory_group_id == memory_group_id)
            .join(Language, Language.language_code == MemoryGroup.memory_language)
        ).scalar_one()
    for batch in batched(chapters, 10):
        with db_factory() as db:
            texts = db.execute(
                select(ChapterContent).where(
                    ChapterContent.chapter_content_id.in_([row._t[1].chapter_content_id for row in batch])
                )
            )
            texts_dict = {r._t[0].chapter_content_id: r._t[0].chapter_content_text for r in texts.all()}
        for row in batch:
            chapter, chapter_content = row._t
            context = MemAccessContext(
                memory_group_id=memory_group_id,
                chapter_id=chapter.chapter_id,
                chapter_content_id=chapter_content.chapter_content_id,
            )
            with db_factory() as db:
                try:
                    result = await run_agent(
                        agent,
                        MemAgentDeps(db=db, mem_access_context=context),
                        texts_dict[chapter_content.chapter_content_id],
                        chapter.chapter_num,
                        language_name,
                    )
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
            yield chapter.chapter_num, result
