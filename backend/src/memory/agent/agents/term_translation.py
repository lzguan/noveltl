"""Term-translation (naming) agent with fixed read-only tools."""

from pydantic_ai import Agent, ModelRetry
from pydantic_ai.capabilities import Toolset

from src.memory.agent.capabilities.term_translation import TermTranslationCapability, TermTranslationOutput
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.prompts.term_translation import (
    TERM_TRANSLATION_CONVENTIONS_INSTRUCTIONS,
    TERM_TRANSLATION_INSTRUCTIONS,
)
from src.memory.agent.registry import model_configuration
from src.memory.agent.toolsets.glossary.definitions import glossary_definitions_read_toolset
from src.memory.agent.toolsets.glossary.relations import glossary_relations_read_toolset
from src.memory.agent.toolsets.translations.tools import translations_read_toolset
from src.memory.agent.types import ModelName


def create_term_translation_agent(
    model_name: ModelName, required_terms: tuple[str, ...], include_conventions: bool
) -> Agent[MemAgentDeps, TermTranslationOutput]:
    model, model_settings = model_configuration(model_name)
    instructions = (
        [TERM_TRANSLATION_INSTRUCTIONS, TERM_TRANSLATION_CONVENTIONS_INSTRUCTIONS]
        if include_conventions
        else TERM_TRANSLATION_INSTRUCTIONS
    )
    agent = Agent(
        model=model,
        model_settings=model_settings,
        deps_type=MemAgentDeps,
        output_type=TermTranslationOutput,
        instructions=instructions,
        capabilities=[
            TermTranslationCapability(),
            Toolset(translations_read_toolset),
            Toolset(glossary_definitions_read_toolset),
            Toolset(glossary_relations_read_toolset),
        ],
    )

    @agent.output_validator
    def validate_requested_terms(output: TermTranslationOutput) -> TermTranslationOutput:
        if {item.term for item in output.translations} != set(required_terms):
            raise ModelRetry("Return each requested source term exactly once, with no additional terms")
        return output

    return agent
