from pydantic import Field

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.plugins.conventions.access import read_conventions
from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.plugins.glossary import access as glossary
from src.memory.plugins.glossary.access import ALIAS_MARKS
from src.memory.plugins.glossary.types import TermKind
from src.memory.plugins.translations.access import read_term_translations
from src.memory.schemas import AgentModel
from src.memory.types import Creator, MemoryType, ReviewStatus

MAX_CONTEXT_TERMS = 200
MAX_MEMORY_CHARS = 200
MAX_CONTEXT_MEMORIES = 2000


class ContextConvention(AgentModel):
    handle: str = Field(description="Handle for revising or withdrawing this convention, such as c3.")
    category: ConventionCategory
    title: str
    rule: str
    rationale: str | None
    review_status: ReviewStatus = Field(description="Rejected conventions must not be proposed again.")
    editable: bool = Field(description="Whether this convention may be revised or withdrawn.")


class ContextTerm(AgentModel):
    term: str = Field(description="Exact source-language form.")
    kind: TermKind | None
    first_chapter_num: int = Field(description="First reviewed chapter containing the term.")
    definition: str | None = Field(description="Current definition, shortened; null if none is recorded.")
    translation: str | None = Field(description="Current canonical rendering; null if the term is not named yet.")
    aliases: list[str] = Field(
        description="Alias relations involving the term, such as a codename and the person or form it belongs to."
    )


class ConventionsContext(AgentModel):
    conventions: list[ContextConvention]
    terms: list[ContextTerm] = Field(
        description="Terms in the reviewed chapters, grouped by kind and earliest first within each kind."
    )
    terms_truncated: bool = Field(description="Whether more terms occur in the range than are listed.")


def _shorten(text: str) -> str:
    return text if len(text) <= MAX_MEMORY_CHARS else text[: MAX_MEMORY_CHARS - 1] + "…"


def conventions_context(deps: MemAgentDeps, start_chapter_num: int | None) -> ConventionsContext:
    db, ctx = deps.db, deps.mem_access_context
    conventions = [
        ContextConvention(
            handle=deps.convention_handles.new(row.convention_id),
            category=row.category,
            title=row.title,
            rule=row.rule,
            rationale=row.rationale,
            review_status=row.review_status,
            editable=row.creator_type == Creator.AGENT and row.review_status == ReviewStatus.PENDING,
        )
        for row in read_conventions(db, ctx.memory_group_id, workspace_id=ctx.workspace_id)
    ]
    range_terms, terms_truncated = glossary.get_terms_in_chapter_range(
        db, ctx, start_chapter_num, limit=MAX_CONTEXT_TERMS
    )
    range_terms.sort(key=lambda row: (row.term.term_kind or "", row.first_chapter_num, row.term.term))
    terms = [row.term for row in range_terms]
    definition_page = glossary.inspect_terms(
        db, ctx, [term.term for term in terms], [MemoryType.DEFINITION], limit=MAX_CONTEXT_MEMORIES
    )
    definitions: dict[str, str] = {}
    for row in definition_page.rows:
        for associated in row.terms:
            definitions.setdefault(associated.term, row.memory.memory_content)
    alias_page = glossary.inspect_terms(
        db,
        ctx,
        [term.term for term in terms],
        [MemoryType.RELATION],
        limit=MAX_CONTEXT_MEMORIES,
        marks=list(ALIAS_MARKS),
    )
    aliases: dict[str, list[str]] = {}
    for row in alias_page.rows:
        for associated in row.terms:
            aliases.setdefault(associated.term, []).append(_shorten(row.memory.memory_content))
    translations = {
        mapping.term: mapping.translation for mapping in read_term_translations(db, ctx, [term.term for term in terms])
    }
    return ConventionsContext(
        conventions=conventions,
        terms=[
            ContextTerm(
                term=row.term.term,
                kind=row.term.term_kind,
                first_chapter_num=row.first_chapter_num,
                definition=_shorten(definitions[row.term.term]) if row.term.term in definitions else None,
                translation=translations.get(row.term.term),
                aliases=aliases.get(row.term.term, []),
            )
            for row in range_terms
        ],
        terms_truncated=terms_truncated,
    )
