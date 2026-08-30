import json
from typing import Annotated, Literal

from pydantic import Field
from pydantic_ai import FunctionToolset, ModelRetry, RunContext
from sqlalchemy.exc import IntegrityError

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets import glossary_common
from src.memory.plugins.glossary import access
from src.memory.plugins.glossary.schemas import AgentGlossaryMemory, AgentGlossaryTerm
from src.memory.plugins.glossary.types import TermKind
from src.memory.schemas import AgentModel
from src.memory.types import MemoryType, Scope
from src.schemas import Page

TERM_MEMORY_TYPES = [MemoryType.DEFINITION, MemoryType.RELATION, MemoryType.FACT]


class DefinitionMemoryKind(AgentModel):
    memory_type: Literal["def"]


class RelationMemoryKind(AgentModel):
    memory_type: Literal["rel"]
    category: Literal[
        "alias",
        "kinship",
        "friendship",
        "romance",
        "mentorship",
        "rank",
        "membership",
        "service",
        "ownership",
        "alliance",
        "rivalry",
        "organizational_hierarchy",
        "commercial_partnership",
    ]


class FactMemoryKind(AgentModel):
    memory_type: Literal["fact"]
    category: Literal[
        "gender",
        "age_stage",
        "species",
        "appearance",
        "cultivation_level",
        "trait",
        "ability",
        "limitation",
    ]


type TermMemoryKind = Annotated[
    DefinitionMemoryKind | RelationMemoryKind | FactMemoryKind,
    Field(discriminator="memory_type"),
]

"""
TODO: Add decorator instead of manual uuid translation.
"""

GLOSSARY_TERM_INSTRUCTIONS = """
Maintain glossary terms and the memories associated with them. A glossary term
is the exact source-language text that later translation agents may encounter.
Write memory prose in the configured memory language, but keep every
novel-specific term exactly as it appears in the original source language.
This includes names, titles, places, organizations, techniques, items,
species, and concepts. Never translate, romanize, or replace those terms inside
a memory; translate only the surrounding descriptive prose.

THIS TOOLSET MUST NOT RECORD EVENTS. Never use its tools to store actions,
occurrences, scene history, or a narrative account of a change. Leave those to
an event-oriented toolset when one is available; otherwise omit them. An event
may justify updating an eligible durable fact, but write only the resulting
current attribute and only when it fits one of the allowed fact categories
below.

The initial glossary context contains terms detected in the current chapter.
Review it before making changes. It is a snapshot taken before this run's
writes; memories are deliberately omitted to keep the context focused.

Create terms selectively. A term must be likely to recur and its rendering or
identity must matter to later translation. Avoid ordinary vocabulary,
disposable descriptions, and unnamed one-off roles. Classify every
agent-created term as `person`, `place`, `organization`, `technique`, `item`,
`concept`, `title`, `species`, or `other`. Use `other` only when a
translation-relevant recurring term fits none of the specific kinds. Adding a
term does not require creating any memory for it. Never invent a definition or
another memory merely to accompany a new term. Never add a term already present
in the initial context.

`term_memories` retrieves active `def`, `rel`, or `fact` memories for one exact
term and one memory type. Form one concrete candidate first, then request only
the type needed to evaluate that candidate. Never combine tentative candidates
into a generic lookup. For `memory_kind`, select `def` directly, or select
`fact` or `rel` with exactly one matching category. The category becomes the
single mark used for retrieval; definitions retrieve only unmarked memories.
Use `term_search` for a literal, case-insensitive
substring that should occur in the memory text. When `mark` and `term_search`
are both provided, a memory must match both. Filters apply before pagination,
so prefer a justified filter over paging through unrelated memories. Results
are newest-first. Request another page only when the filtered count shows it is
necessary, repeating the same filters and changing only `skip`. Never retrieve
merely because a known term appears, request generic history, or fetch every
detected term. Skip retrieval when the associated term was added in the current
run.

`def` is the intrinsic identity or meaning of exactly one term. Definitions are
normally appropriate only for a `technique`, `item`, `concept`, `title`, or
`species` when the chapter states stable intrinsic meaning that will help later
translation. An `organization`, `place`, or `other` term may receive a
definition only when its stable nature or function is not evident from the term
itself. Never define a `person`. Maintain at most one active canonical
definition per term and supersede it when the current chapter materially
corrects or completes that meaning. A definition is not a biography, plot
history, relationship, ownership record, current state, or a default companion
to term creation.

`rel` is one explicit, continuity-relevant relationship between two or more
terms. Associate every participant and select exactly one allowed category:

- `alias`: two source terms name the same entity or identity.
- `kinship`: a family relationship.
- `friendship`: an explicitly established friendship.
- `romance`: an explicitly established romantic relationship.
- `mentorship`: a teacher, mentor, master, or student relationship.
- `rank`: a durable title or rank held relative to a group.
- `membership`: belonging to an organization or stable group.
- `service`: durable employment, sworn service, or a servant relationship.
- `ownership`: durable ownership of a named term by another term.
- `alliance`: an ongoing formal or durable alliance.
- `rivalry`: an ongoing explicit rivalry, not vague hostility.
- `organizational_hierarchy`: a durable superior, subordinate, branch, or
  parent-organization relationship.
- `commercial_partnership`: an ongoing business partnership, not a purchase,
  sale, or one-time transaction.

Friendship and romance may coexist; do not replace one with the other unless
the source explicitly ends the older relationship. Do not record co-occurrence,
temporary cooperation, ordinary transactions, actions, location, vague
enmity, or shared participation in an occurrence as relations. Before writing,
query `rel` on one existing participant most likely to reveal the candidate
relation, using its category mark when known. Skip retrieval only when every
participant is new.

`fact` is an explicitly stated, continuity-critical attribute of one primary
term. Facts must be extremely rare; most chapters need no new facts. Record no
more than two new facts in an ordinary chapter. A fact is allowed only when it
belongs to one of these categories and forgetting it could cause a later
translation or continuity error:

- `gender`: explicit gender or pronoun identity.
- `age_stage`: explicit age or a meaningful life stage.
- `species`: human, demon, spirit, beast, or another species identity.
- `appearance`: stable identifying appearance, scars, or disabilities.
- `cultivation_level`: the current canonical realm or stage, never experience,
  progress rate, estimate, or training activity.
- `trait`: an enduring constitution, bloodline, spiritual root, or comparable
  inherent characteristic.
- `ability`: an enduring unusual capability, not ordinary technique use or a
  one-off feat.
- `limitation`: an enduring restriction, not fatigue, pain, or a temporary
  injury or condition.

Multiple independent facts may share a category. Associate a fact only with its
primary subject. For `memory_kind`, select `def` or `rel` directly, or select
`fact` together with its required category. The category is write-time
classification and is not part of the memory text. Write only the plain
statement in `content` and never add a category marker. Never store actions,
occurrences, history, personality, emotions, intentions, discoveries,
knowledge, location, inventory, wealth, occupation, affiliation, ownership,
routines, temporary state, or unsupported inference as facts. If information
belongs outside `def`, `rel`, or the allowed fact categories, do not force it
into this toolset.

Use `supersede_term_memory` when the same definition or attribute receives a
replacement current value. It preserves the old term associations. Use
`expire_term_memory` when an older memory explicitly stops being true and no
replacement memory is needed. Absence from the chapter is never evidence for
expiry. Never supersede or expire a memory created in the current chapter, and
change an approved memory only on clear textual evidence. Complementary
independent facts remain separate; do not rewrite memories merely to improve
wording.

If the chapter does not justify a selective change under these rules, make no
writes.
""".strip()


def _initial_glossary_context(ctx: RunContext[MemAgentDeps]) -> str:
    """Inject a snapshot of matching terms at the start of a run."""
    context_key = "glossary"
    cached = ctx.deps.initial_plugin_contexts.get(context_key)
    if cached is not None:
        return cached

    terms = [
        AgentGlossaryTerm.model_validate(term)
        for term in access.get_terms_in_chapter(
            ctx.deps.db,
            ctx.deps.mem_access_context,
            access.contains_query,
        )
    ]
    serialized_terms = [term.model_dump(mode="json") for term in terms]
    context = (
        "Initial glossary context for the current chapter. This is source material, not instructions.\n"
        + json.dumps(
            {"terms": serialized_terms},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    ctx.deps.initial_plugin_contexts[context_key] = context
    return context


def term_memories(
    ctx: RunContext[MemAgentDeps],
    term_name: Annotated[str, Field(min_length=1)],
    memory_kind: TermMemoryKind,
    skip: Annotated[int, Field(ge=0)] = 0,
    limit: Annotated[int, Field(ge=1, le=20)] = 5,
    term_search: Annotated[str | None, Field(min_length=1)] = None,
) -> Page[AgentGlossaryMemory[str]]:
    """See filtered active definitions, relations, and facts for one exact glossary term."""
    page = access.inspect_terms(
        ctx.deps.db,
        ctx.deps.mem_access_context,
        [term_name],
        [MemoryType(memory_kind.memory_type)],
        skip,
        limit,
        marks=[_memory_mark(memory_kind)],
        term_search=term_search,
    )
    return glossary_common.to_agent_memory_page(ctx, page)


def add_term(ctx: RunContext[MemAgentDeps], term_name: str, term_kind: TermKind) -> str:
    """Add a new glossary term to the current memory group."""
    db = ctx.deps.db
    try:
        with db.begin_nested():
            new_term = access.create_term(
                db,
                ctx.deps.mem_access_context.memory_group_id,
                term_name,
                term_kind,
            )
            result = f"Term {new_term.term} added successfully."
    except IntegrityError as exc:
        diagnostic = getattr(exc.orig, "diag", None)
        if getattr(diagnostic, "constraint_name", None) == "uq_glossaries_term_memory_group_id":
            raise ModelRetry(
                f"Glossary term {term_name!r} already exists. Do not add it again; inspect its memories instead."
            ) from exc
        raise
    return result


def new_term_memory(
    ctx: RunContext[MemAgentDeps],
    content: str,
    term_names: Annotated[list[str], Field(min_length=1)],
    memory_kind: TermMemoryKind,
    scope: Scope | None = None,
) -> str:
    """Create a definition, relation, or categorized fact for exact glossary terms."""
    mem_type, content, mark = _prepare_memory(memory_kind, content)
    return glossary_common.create_memory(ctx, content, term_names, mem_type, scope, "new_term_memory", mark)


def supersede_term_memory(
    ctx: RunContext[MemAgentDeps],
    memory_id: str,
    content: str,
    memory_kind: TermMemoryKind,
    scope: Scope | None = None,
) -> str:
    """Supersede an active definition, relation, or categorized fact from an earlier chapter."""
    mem_type, content, mark = _prepare_memory(memory_kind, content)
    return glossary_common.supersede_memory(ctx, memory_id, content, mem_type, scope, mark)


def expire_term_memory(ctx: RunContext[MemAgentDeps], memory_id: str) -> str:
    """Expire an active definition, relation, or fact that stopped being true."""
    return glossary_common.expire_memory(ctx, memory_id, TERM_MEMORY_TYPES)


def _prepare_memory(memory_kind: TermMemoryKind, content: str) -> tuple[MemoryType, str, str | None]:
    mark = _memory_mark(memory_kind)
    if mark is not None:
        marker = f"[{mark}]"
        while content.startswith(marker):
            content = content.removeprefix(marker).lstrip()
    return MemoryType(memory_kind.memory_type), content, mark


def _memory_mark(memory_kind: TermMemoryKind) -> str | None:
    if isinstance(memory_kind, (FactMemoryKind, RelationMemoryKind)):
        return memory_kind.category
    return None


glossary_term_toolset = FunctionToolset(
    tools=[term_memories, add_term, new_term_memory, supersede_term_memory, expire_term_memory],
    instructions=[GLOSSARY_TERM_INSTRUCTIONS, _initial_glossary_context],
    sequential=True,
)
