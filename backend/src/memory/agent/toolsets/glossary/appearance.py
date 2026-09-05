"""Character appearance writes, separate from identity and capabilities."""

from typing import Annotated, Literal, get_args

from pydantic import Field
from pydantic_ai import FunctionToolset, RunContext

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.glossary import common
from src.memory.types import MemoryType, Scope

type AppearanceField = Literal["hair", "eyes", "markings", "stature_build", "anatomy", "apparent_age", "attire"]
APPEARANCE_MARKS = {field: f"appearance.{field}" for field in get_args(AppearanceField.__value__)}

APPEARANCE_INSTRUCTIONS = """
Maintain explicit, identifying appearance of individual characters. Allowed
fields are hair, eyes, persistent markings (scars, birthmarks, tattoos), stature
and build, distinctive anatomy, apparent age, and recurring attire. Keep one
focused claim per memory, and only when it matters to later identification.
Attire includes a recurring outfit, uniform, or identifying worn accessory;
exclude routine clothing changes, ordinary inventory, prices, and disposable
scene details. Do not record attractiveness judgments, poses, expressions,
temporary injury, grooming routines, or infer gender from appearance.

"林渊 looks like a child" is apparent_age, not actual age_stage. "林渊 has
wings" is anatomy, not evidence of flight. "林渊 wears the academy's white
uniform" may be attire; it does not establish membership or identity.
Gendered body state and self-identity belong to gender writers. Do not copy
those claims into anatomy. A costume does not establish a disguise or an
observer's belief. Defer temporary or alternating form-specific descriptions
until form-aware state is supported; do not overwrite canonical appearance
each time a character transforms.

Before every candidate, use character_state_memories for the exact character,
unless the term is newly created. Inspect relevant pages and original marks.
No write is needed for a represented claim. Supersede the same feature when
its persistent value changes; independent features can coexist. Expire only
when the feature explicitly ends without replacement. Absence is not expiry.
Read access does not authorize changing another writer's records. Legacy
appearance facts remain readable; do not duplicate one merely to categorize it.
""".strip()


def new_appearance_memory(
    ctx: RunContext[MemAgentDeps],
    term_name: Annotated[str, Field(min_length=1)],
    field: AppearanceField,
    content: str,
    scope: Scope | None = None,
) -> str:
    """Record one identifying feature or recurring attire claim."""
    mark = APPEARANCE_MARKS[field]
    return common.create_memory(
        ctx,
        common.strip_marker(content, mark),
        [term_name],
        MemoryType.FACT,
        scope,
        "new_appearance_memory",
        mark,
    )


def supersede_appearance_memory(
    ctx: RunContext[MemAgentDeps],
    memory_id: str,
    term_name: Annotated[str, Field(min_length=1)],
    field: AppearanceField,
    content: str,
    scope: Scope | None = None,
) -> str:
    """Replace the same feature, including a legacy unstructured appearance fact."""
    mark = APPEARANCE_MARKS[field]
    return common.supersede_memory(
        ctx,
        memory_id,
        common.strip_marker(content, mark),
        MemoryType.FACT,
        scope,
        mark,
        replacement_term_names=[term_name],
        expected_marks=[mark, "appearance"],
    )


def expire_appearance_memory(ctx: RunContext[MemAgentDeps], memory_id: str) -> str:
    """End an appearance claim without affecting other character domains."""
    return common.expire_memory(
        ctx,
        memory_id,
        [MemoryType.FACT],
        marks=["appearance", *APPEARANCE_MARKS.values()],
    )


glossary_appearance_write_toolset = FunctionToolset(
    tools=[new_appearance_memory, supersede_appearance_memory, expire_appearance_memory],
    instructions=[APPEARANCE_INSTRUCTIONS],
    sequential=True,
)
