from collections.abc import Callable

from pydantic_ai import Agent, FunctionToolset, ModelRetry
from pydantic_ai.capabilities import AbstractCapability, Toolset
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.profiles.openai import OpenAIJsonSchemaTransformer, OpenAIModelProfile
from pydantic_ai.providers.openai import OpenAIProvider

from src.config import inception_settings
from src.memory.agent.capabilities.continuity import ContinuitySummaryCapability, ContinuitySummaryOutput
from src.memory.agent.capabilities.term_translation import TermTranslationCapability, TermTranslationOutput
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.prompts.recording import MEMORY_AGENT_PROMPT
from src.memory.agent.prompts.term_translation import (
    TERM_TRANSLATION_CONVENTIONS_INSTRUCTIONS,
    TERM_TRANSLATION_INSTRUCTIONS,
)
from src.memory.agent.toolsets.glossary.aliases import glossary_aliases_write_toolset
from src.memory.agent.toolsets.glossary.appearance import glossary_appearance_write_toolset
from src.memory.agent.toolsets.glossary.character_state import glossary_character_state_read_toolset
from src.memory.agent.toolsets.glossary.context import GLOSSARY_SHARED_INSTRUCTIONS, initial_glossary_context
from src.memory.agent.toolsets.glossary.cultivation import glossary_cultivation_write_toolset
from src.memory.agent.toolsets.glossary.definitions import (
    glossary_definitions_read_toolset,
    glossary_definitions_write_toolset,
)
from src.memory.agent.toolsets.glossary.events import glossary_events_read_toolset, glossary_events_write_toolset
from src.memory.agent.toolsets.glossary.facts import glossary_facts_write_toolset
from src.memory.agent.toolsets.glossary.gender_advanced_events import (
    create_glossary_gender_advanced_events_write_toolset,
    glossary_gender_advanced_events_read_toolset,
)
from src.memory.agent.toolsets.glossary.gender_advanced_facts import (
    glossary_gender_advanced_facts_write_toolset,
)
from src.memory.agent.toolsets.glossary.gender_advanced_relations import (
    glossary_gender_advanced_relations_write_toolset,
)
from src.memory.agent.toolsets.glossary.guidance.artifacts import glossary_artifact_toolset
from src.memory.agent.toolsets.glossary.guidance.gender_transformation import (
    glossary_gender_transformation_toolset,
)
from src.memory.agent.toolsets.glossary.impersonation import glossary_impersonation_write_toolset
from src.memory.agent.toolsets.glossary.relations import (
    glossary_relations_read_toolset,
    glossary_relations_write_toolset,
)
from src.memory.agent.toolsets.glossary.terms import glossary_term_toolset
from src.memory.agent.toolsets.translations.tools import translations_read_toolset
from src.memory.agent.types import (
    TOOLSET_NAMES,
    ModelName,
    OccurrenceRetentionConfig,
    ParsedToolsets,
    ToolsetConfig,
    ToolsetName,
)

type CapabilityFactory = Callable[[ToolsetConfig], AbstractCapability[MemAgentDeps]]


def _toolset_capability(toolset: FunctionToolset[MemAgentDeps]) -> CapabilityFactory:
    def resolve(_: ToolsetConfig) -> AbstractCapability[MemAgentDeps]:
        return Toolset(toolset)

    return resolve


def _advanced_gender_events_write(config: ToolsetConfig) -> AbstractCapability[MemAgentDeps]:
    if not isinstance(config, OccurrenceRetentionConfig):
        raise TypeError("Advanced gender event writes require OccurrenceRetentionConfig")
    return Toolset(create_glossary_gender_advanced_events_write_toolset(config))


capability_factories_by_name: dict[ToolsetName, CapabilityFactory] = {
    "continuity_summary": lambda _: ContinuitySummaryCapability(),
    "glossary_terms": _toolset_capability(glossary_term_toolset),
    "glossary_definitions_read": _toolset_capability(glossary_definitions_read_toolset),
    "glossary_definitions_write": _toolset_capability(glossary_definitions_write_toolset),
    "glossary_relations_read": _toolset_capability(glossary_relations_read_toolset),
    "glossary_relations_write": _toolset_capability(glossary_relations_write_toolset),
    "glossary_aliases_write": _toolset_capability(glossary_aliases_write_toolset),
    "glossary_impersonation_write": _toolset_capability(glossary_impersonation_write_toolset),
    "glossary_character_read": _toolset_capability(glossary_character_state_read_toolset),
    "glossary_character_write": _toolset_capability(glossary_facts_write_toolset),
    "glossary_appearance_write": _toolset_capability(glossary_appearance_write_toolset),
    "glossary_cultivation_write": _toolset_capability(glossary_cultivation_write_toolset),
    "glossary_gender_advanced_facts_write": _toolset_capability(glossary_gender_advanced_facts_write_toolset),
    "glossary_gender_advanced_relations_write": _toolset_capability(glossary_gender_advanced_relations_write_toolset),
    "glossary_events_read": _toolset_capability(glossary_events_read_toolset),
    "glossary_events_write": _toolset_capability(glossary_events_write_toolset),
    "glossary_gender_advanced_events_read": _toolset_capability(glossary_gender_advanced_events_read_toolset),
    "glossary_gender_advanced_events_write": _advanced_gender_events_write,
    "glossary_gender_transformation": _toolset_capability(glossary_gender_transformation_toolset),
    "glossary_artifacts": _toolset_capability(glossary_artifact_toolset),
}

if set(capability_factories_by_name) != set(TOOLSET_NAMES):
    raise RuntimeError("Memory-agent capability registry does not match TOOLSET_NAMES")

GLOSSARY_TOOLSET_NAMES: frozenset[ToolsetName] = frozenset(
    name for name in TOOLSET_NAMES if name != "continuity_summary"
)

MERCURY_PROFILE = OpenAIModelProfile(
    json_schema_transformer=OpenAIJsonSchemaTransformer,
    supports_json_schema_output=True,  # response_format json_schema returned valid JSON
    supports_json_object_output=True,  # json_object mode likewise
    supports_thinking=True,  # REQUIRED - see below
    openai_supports_strict_tool_definition=True,
    openai_supports_tool_choice_required=True,  # "required" and named forcing both accepted
    openai_reasoning_enabled_by_default=True,  # omitting the param spends ~200-260 reasoning tokens
    openai_chat_supports_multiple_system_messages=True,
    context_window=260_000,
)


def resolve_capabilities(toolsets: ParsedToolsets) -> list[AbstractCapability[MemAgentDeps]]:
    """Resolve configured capabilities in canonical order for stable prompt caching."""
    resolved: list[AbstractCapability[MemAgentDeps]] = []
    for name in toolsets.selected_names():
        config = getattr(toolsets, name)
        if config is None:
            raise RuntimeError(f"Selected toolset {name} has no configuration")
        resolved.append(capability_factories_by_name[name](config))
    return resolved


def model_configuration(model_name: ModelName) -> tuple[Model | str, OpenAIChatModelSettings]:
    """Resolve provider configuration shared by the two agent factories."""
    model: Model | str
    model_settings: OpenAIChatModelSettings
    if model_name == "deepseek:deepseek-v4-flash-none":
        model = "deepseek:deepseek-v4-flash"
        model_settings = {"extra_body": {"thinking": {"type": "disabled"}}}
    elif model_name == "deepseek:deepseek-v4-flash-low":
        model = "deepseek:deepseek-v4-flash"
        model_settings = {"thinking": "low"}
    elif model_name == "inception:mercury-2.5-low":
        model = OpenAIChatModel(
            "mercury-2.5",
            provider=OpenAIProvider(
                api_key=inception_settings.INCEPTION_API_KEY, base_url=inception_settings.INCEPTION_API_URL
            ),
            profile=MERCURY_PROFILE,
        )
        model_settings = {"thinking": "low"}
    else:
        raise ValueError(f"Unknown model name {model_name!r}")
    return model, model_settings


def create_recording_agent(
    model_name: ModelName, toolsets: ParsedToolsets
) -> Agent[MemAgentDeps, str | ContinuitySummaryOutput]:
    model, model_settings = model_configuration(model_name)
    resolved_capabilities = resolve_capabilities(toolsets)
    glossary_enabled = any(toolset in GLOSSARY_TOOLSET_NAMES for toolset in toolsets.selected_names())
    instructions = (
        [MEMORY_AGENT_PROMPT, GLOSSARY_SHARED_INSTRUCTIONS, initial_glossary_context]
        if glossary_enabled
        else MEMORY_AGENT_PROMPT
    )
    return Agent(
        model=model,
        model_settings=model_settings,
        capabilities=resolved_capabilities,
        instructions=instructions,
        deps_type=MemAgentDeps,
        output_type=ContinuitySummaryOutput if toolsets.continuity_summary is not None else str,
    )


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
