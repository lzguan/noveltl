import uuid
from itertools import batched
from typing import Literal

from pydantic_ai import Agent, AgentRunResult, FunctionToolset
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased, defer, sessionmaker

from src.memory.access import MemAccessContext
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.prompts.prompt import MEMORY_AGENT_PROMPT
from src.memory.agent.toolsets.glossary import glossary_toolset
from src.memory.models import MemoryGroup
from src.novels.models import Chapter, ChapterContent

type PluginName = Literal["glossary"]

plugin_toolsets: dict[PluginName, FunctionToolset] = {"glossary": glossary_toolset}

type ModelName = Literal["deepseek:deepseek-chat"]


def create_agent(model_name: ModelName, plugins: list[PluginName]) -> Agent[MemAgentDeps, str]:
    """Create a Pydantic AI agent with the specified model and plugins."""
    return Agent(
        model=model_name, toolsets=[plugin_toolsets[plugin] for plugin in plugins], instructions=MEMORY_AGENT_PROMPT
    )


async def run_agent(
    agent: Agent, deps: MemAgentDeps, chapter_text: str, chapter_num: int, language_code: str
) -> AgentRunResult:
    """Run the agent with the given input text and dependencies."""

    prompt = f"Record new terms and memories in the language {language_code} from the following chapter text (chapter {chapter_num}):\n\n{chapter_text}"
    return await agent.run(
        prompt,
        deps=deps,
    )


async def run_novel(db_factory: sessionmaker[Session], agent: Agent, novel_id: uuid.UUID, memory_group_id: uuid.UUID):
    latest_chapter_content = aliased(ChapterContent)
    with db_factory() as db:
        chapters = db.execute(
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
        ).all()
        language_code = db.execute(
            select(MemoryGroup.memory_language).where(MemoryGroup.memory_group_id == memory_group_id)
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
            result = await run_agent(
                agent,
                MemAgentDeps(db_factory=db_factory, mem_access_context=context, job_id=uuid.uuid4()),
                texts_dict[chapter_content.chapter_content_id],
                chapter.chapter_num,
                language_code,
            )
            print(f"Chapter {chapter.chapter_num} result: {result}")
