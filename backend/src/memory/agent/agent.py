from pydantic_ai import Agent, AgentRunResult, FunctionToolset
from pydantic_ai.models.openai import OpenAIChatModelSettings

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.prompts.prompt import MEMORY_AGENT_PROMPT
from src.memory.agent.toolsets.glossary.context import GLOSSARY_SHARED_INSTRUCTIONS, initial_glossary_context
from src.memory.agent.toolsets.glossary.definitions import (
    glossary_definitions_read_toolset,
    glossary_definitions_write_toolset,
)
from src.memory.agent.toolsets.glossary.events import glossary_events_read_toolset, glossary_events_write_toolset
from src.memory.agent.toolsets.glossary.facts import glossary_facts_read_toolset, glossary_facts_write_toolset
from src.memory.agent.toolsets.glossary.gender import glossary_gender_read_toolset, glossary_gender_write_toolset
from src.memory.agent.toolsets.glossary.gender_advanced_events import (
    glossary_gender_advanced_events_read_toolset,
    glossary_gender_advanced_events_write_toolset,
)
from src.memory.agent.toolsets.glossary.gender_advanced_facts import (
    glossary_gender_advanced_facts_read_toolset,
    glossary_gender_advanced_facts_write_toolset,
)
from src.memory.agent.toolsets.glossary.guidance.artifacts import glossary_artifact_toolset
from src.memory.agent.toolsets.glossary.guidance.cultivation import glossary_cultivation_toolset
from src.memory.agent.toolsets.glossary.guidance.gender_transformation import (
    glossary_gender_transformation_toolset,
)
from src.memory.agent.toolsets.glossary.guidance.system import glossary_system_toolset
from src.memory.agent.toolsets.glossary.relations import (
    glossary_relations_read_toolset,
    glossary_relations_write_toolset,
)
from src.memory.agent.toolsets.glossary.terms import glossary_term_toolset
from src.memory.agent.types import TOOLSET_NAMES, ModelName, ToolsetName, validate_toolset_selection

toolsets_by_name: dict[ToolsetName, FunctionToolset[MemAgentDeps]] = {
    "glossary_terms": glossary_term_toolset,
    "glossary_definitions_read": glossary_definitions_read_toolset,
    "glossary_definitions_write": glossary_definitions_write_toolset,
    "glossary_relations_read": glossary_relations_read_toolset,
    "glossary_relations_write": glossary_relations_write_toolset,
    "glossary_facts_read": glossary_facts_read_toolset,
    "glossary_facts_write": glossary_facts_write_toolset,
    "glossary_gender_read": glossary_gender_read_toolset,
    "glossary_gender_write": glossary_gender_write_toolset,
    "glossary_gender_advanced_facts_read": glossary_gender_advanced_facts_read_toolset,
    "glossary_gender_advanced_facts_write": glossary_gender_advanced_facts_write_toolset,
    "glossary_events_read": glossary_events_read_toolset,
    "glossary_events_write": glossary_events_write_toolset,
    "glossary_gender_advanced_events_read": glossary_gender_advanced_events_read_toolset,
    "glossary_gender_advanced_events_write": glossary_gender_advanced_events_write_toolset,
    "glossary_gender_transformation": glossary_gender_transformation_toolset,
    "glossary_cultivation": glossary_cultivation_toolset,
    "glossary_system": glossary_system_toolset,
    "glossary_artifacts": glossary_artifact_toolset,
}

if set(toolsets_by_name) != set(TOOLSET_NAMES):
    raise RuntimeError("Memory-agent toolset registry does not match TOOLSET_NAMES")

GLOSSARY_TOOLSET_NAMES: frozenset[ToolsetName] = frozenset(TOOLSET_NAMES)


def resolve_toolsets(toolsets: list[ToolsetName]) -> list[FunctionToolset[MemAgentDeps]]:
    """Validate and resolve names in canonical order for stable prompt caching."""

    validate_toolset_selection(toolsets)
    selected = set(toolsets)
    return [toolsets_by_name[name] for name in TOOLSET_NAMES if name in selected]


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
    resolved_toolsets = resolve_toolsets(toolsets)
    glossary_enabled = any(toolset in GLOSSARY_TOOLSET_NAMES for toolset in toolsets)
    instructions = (
        [MEMORY_AGENT_PROMPT, GLOSSARY_SHARED_INSTRUCTIONS, initial_glossary_context]
        if glossary_enabled
        else MEMORY_AGENT_PROMPT
    )
    return Agent(
        model="deepseek:deepseek-v4-flash",
        model_settings=model_settings,
        toolsets=resolved_toolsets,
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
