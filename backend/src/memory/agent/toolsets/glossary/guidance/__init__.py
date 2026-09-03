from pydantic_ai import FunctionToolset

from src.memory.agent.dependencies import MemAgentDeps


def create_guidance_toolset(name: str, instructions: str) -> FunctionToolset[MemAgentDeps]:
    """Create an instruction-only toolset with no callable tools."""

    return FunctionToolset(tools=[], id=name, instructions=[instructions])
