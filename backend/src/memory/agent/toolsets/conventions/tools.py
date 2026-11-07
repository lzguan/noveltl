"""Read-only tools for the conventions agent."""

from typing import Annotated

from pydantic import Field
from pydantic_ai import FunctionToolset, RunContext

from src.memory.access import check_mem_access_ctx
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.plugins.glossary import access as glossary
from src.memory.plugins.glossary.types import TermKind
from src.memory.plugins.translations.access import read_term_translations
from src.memory.schemas import AgentModel
from src.novels.term_search import summarize_occurrences

MAX_SEARCH_RESULTS = 30

CONVENTIONS_TOOLS_INSTRUCTIONS = """
`search_glossary_terms` finds glossary terms whose name contains a substring,
including terms outside the reviewed chapters; use it to find term families
such as every term containing 级. `term_occurrences` reports where exact texts
occur up to the last reviewed chapter, including texts that are not glossary
terms.
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


def search_glossary_terms(
    ctx: RunContext[MemAgentDeps], query: Annotated[str, Field(min_length=1, max_length=50)]
) -> TermSearchResult:
    """Find glossary terms whose source form contains the query, with their current translations."""
    db, access_ctx = ctx.deps.db, ctx.deps.mem_access_context
    count, terms = glossary.search_terms(db, access_ctx.memory_group_id, query, limit=MAX_SEARCH_RESULTS)
    translations = {
        mapping.term: mapping.translation for mapping in read_term_translations(db, access_ctx, [t.term for t in terms])
    }
    return TermSearchResult(
        count=count,
        terms=[FoundTerm(term=t.term, kind=t.term_kind, translation=translations.get(t.term)) for t in terms],
    )


def term_occurrences(
    ctx: RunContext[MemAgentDeps], texts: Annotated[list[str], Field(min_length=1, max_length=20)]
) -> list[TermOccurrences]:
    """Report where exact source texts occur in the novel up to the last reviewed chapter."""
    end_chapter_num, novel_id = check_mem_access_ctx(ctx.deps.db, ctx.deps.mem_access_context)
    return [
        TermOccurrences(
            term=summary.term,
            first_chapter_num=summary.first_chapter_num,
            chapter_count=summary.chapter_count,
            match_count=summary.match_count,
        )
        for summary in summarize_occurrences(ctx.deps.db, novel_id, texts, end_chapter_num)
    ]


conventions_read_toolset = FunctionToolset(
    tools=[search_glossary_terms, term_occurrences],
    instructions=[CONVENTIONS_TOOLS_INSTRUCTIONS],
    sequential=True,
)
