from typing import Annotated

from pydantic import Field
from pydantic_ai import FunctionToolset, RunContext

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.transactions import tool_transaction
from src.memory.plugins.glossary import access as glossary
from src.memory.plugins.glossary.types import TermKind
from src.memory.plugins.term_search.access import count_text_occurrences
from src.memory.plugins.translations.access import read_term_translations
from src.memory.schemas import AgentModel

MAX_SEARCH_RESULTS = 30

CONVENTIONS_TOOLS_INSTRUCTIONS = """
`search_glossary_terms` finds glossary terms whose name contains a substring,
including terms outside the reviewed chapters; use it to find term families
such as every term containing 级. `term_occurrences` reports where exact texts
occur up to the last reviewed chapter, including texts that are not glossary
terms.
Use searches to check a family's pattern and exceptions; the returned terms do
not all need to appear as examples in a convention. Occurrence counts establish
usage frequency, not a preferred translation or prose style.
""".strip()


class FoundTerm(AgentModel):
    term: str
    kind: TermKind | None
    translation: str | None = Field(description="Current canonical rendering; null if not named yet.")


class TermSearchResult(AgentModel):
    count: int = Field(description="Number of matching terms, including any not listed.")
    terms: list[FoundTerm]


class TermOccurrences(AgentModel):
    term: str
    first_chapter_num: int | None = Field(description="First chapter containing the text; null if none does.")
    chapter_count: int = Field(description="Number of chapters containing the text.")
    match_count: int = Field(description="Number of occurrences across those chapters.")


@tool_transaction
def search_glossary_terms(
    ctx: RunContext[MemAgentDeps], query: Annotated[str, Field(min_length=1, max_length=50)]
) -> TermSearchResult:
    """Find glossary terms whose source form contains the query, with their current translations."""
    db, access_ctx = ctx.deps.db, ctx.deps.mem_access_context
    count, terms = glossary.search_terms(
        db, access_ctx.memory_group_id, query, limit=MAX_SEARCH_RESULTS, workspace_id=access_ctx.workspace_id
    )
    translations = {
        mapping.term: mapping.translation for mapping in read_term_translations(db, access_ctx, [t.term for t in terms])
    }
    return TermSearchResult(
        count=count,
        terms=[FoundTerm(term=t.term, kind=t.term_kind, translation=translations.get(t.term)) for t in terms],
    )


@tool_transaction
def term_occurrences(
    ctx: RunContext[MemAgentDeps],
    texts: Annotated[list[Annotated[str, Field(min_length=1)]], Field(min_length=1, max_length=20)],
) -> list[TermOccurrences]:
    """Report where exact source texts occur in the novel up to the last reviewed chapter."""
    return [
        TermOccurrences(
            term=result.text,
            first_chapter_num=result.first_chapter_num,
            chapter_count=result.chapter_count,
            match_count=result.match_count,
        )
        for result in count_text_occurrences(ctx.deps.db, ctx.deps.mem_access_context, texts)
    ]


conventions_read_toolset = FunctionToolset(
    tools=[search_glossary_terms, term_occurrences],
    instructions=[CONVENTIONS_TOOLS_INSTRUCTIONS],
    sequential=True,
)
