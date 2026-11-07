from pydantic_ai import AgentRunResult

from src.memory.agent.agents.conventions import create_conventions_agent
from src.memory.agent.capabilities.conventions import ConventionsOutput
from src.memory.agent.config import SummarizeConventionsStageConfig
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.prompts.conventions import conventions_request_prompt
from src.memory.agent.toolsets.conventions.context import conventions_context


async def run_conventions_stage(
    deps: MemAgentDeps, chapter_num: int, language_name: str, config: SummarizeConventionsStageConfig
) -> AgentRunResult[ConventionsOutput] | None:
    """Run the conventions agent over chapters from ``config.since_chapter_num`` to ``chapter_num``.

    Returns:
        The run result, or None when no glossary terms occur in the range and the model is not called.
    """
    context = conventions_context(deps, config.since_chapter_num)
    if not context.terms:
        return None
    agent = create_conventions_agent(config.model_name)
    async with agent:
        return await agent.run(
            conventions_request_prompt(context, chapter_num, config.since_chapter_num, language_name), deps=deps
        )
