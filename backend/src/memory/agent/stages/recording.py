from pydantic_ai import AgentRunResult

from src.memory.agent.agent import create_recording_agent
from src.memory.agent.capabilities.continuity import ContinuitySummaryOutput
from src.memory.agent.config import RecordMemoriesStageConfig
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.prompts.recording import recording_request_prompt


async def run_recording_stage(
    deps: MemAgentDeps, chapter_text: str, chapter_num: int, language_name: str, config: RecordMemoriesStageConfig
) -> AgentRunResult[str | ContinuitySummaryOutput]:
    agent = create_recording_agent(config.model_name, config.parse_toolsets())
    async with agent:
        return await agent.run(
            recording_request_prompt(chapter_text, chapter_num, language_name),
            deps=deps,
        )
