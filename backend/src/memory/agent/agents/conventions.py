"""Conventions agent: proposes, revises, and withdraws naming conventions for a chapter range."""

from pydantic_ai import Agent
from pydantic_ai.capabilities import Toolset

from src.memory.agent.capabilities.conventions import ConventionsOutput, write_conventions_output
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.prompts.conventions import CONVENTIONS_INSTRUCTIONS
from src.memory.agent.registry import model_configuration
from src.memory.agent.toolsets.conventions.tools import conventions_read_toolset
from src.memory.agent.toolsets.glossary.definitions import glossary_definitions_read_toolset
from src.memory.agent.toolsets.glossary.relations import glossary_relations_read_toolset
from src.memory.agent.toolsets.translations.tools import translations_read_toolset
from src.memory.agent.types import ModelName


def create_conventions_agent(model_name: ModelName) -> Agent[MemAgentDeps, ConventionsOutput]:
    """Create the conventions agent; its output validator writes the output in the run's session."""
    model, model_settings = model_configuration(model_name)
    agent = Agent(
        model=model,
        model_settings=model_settings,
        deps_type=MemAgentDeps,
        output_type=ConventionsOutput,
        instructions=CONVENTIONS_INSTRUCTIONS,
        capabilities=[
            Toolset(conventions_read_toolset),
            Toolset(translations_read_toolset),
            Toolset(glossary_definitions_read_toolset),
            Toolset(glossary_relations_read_toolset),
        ],
    )
    agent.output_validator(write_conventions_output)
    return agent
