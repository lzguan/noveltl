from pydantic_ai import AgentRunResult

from src.memory.agent.agents.conventions import create_conventions_agent
from src.memory.agent.capabilities.conventions import ConventionsOutput
from src.memory.agent.config import SummarizeConventionsStageConfig
from src.memory.agent.dependencies import MemAgentDeps


async def run_conventions_stage(
    deps: MemAgentDeps, chapter_num: int, language_name: str, config: SummarizeConventionsStageConfig
) -> AgentRunResult[ConventionsOutput]:
    agent = create_conventions_agent(config.model_name)
    async with agent:
        return await agent.run("", deps=deps)
