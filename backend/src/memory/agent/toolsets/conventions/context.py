"""Initial context for the conventions agent."""

from pydantic import Field

from src.memory.access import check_mem_access_ctx
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.plugins.conventions.access import read_conventions
from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.plugins.glossary import access as glossary
from src.memory.plugins.glossary.types import TermKind
from src.memory.plugins.translations.access import read_term_translations
from src.memory.schemas import AgentModel
from src.memory.types import Creator, MemoryType, ReviewStatus

MAX_CONTEXT_TERMS = 200
MAX_DEFINITION_CHARS = 200


class ContextConvention(AgentModel):
    """An existing naming convention as shown to the conventions agent."""

    handle: str = Field(description="Handle for revising or withdrawing this convention, such as c3.")
    title: str
    rule: str
    rationale: str | None
    review_status: ReviewStatus = Field(description="Rejected conventions must not be proposed again.")
    editable: bool = Field(description="Whether this convention may be revised or withdrawn.")


class ContextTerm(AgentModel):
    """A glossary term occurring in the reviewed chapters."""

    term: str = Field(description="Exact source-language form.")
    kind: TermKind | None
    first_chapter_num: int = Field(description="First reviewed chapter containing the term.")
    definition: str | None = Field(description="Current definition, shortened; null if none is recorded.")
    translation: str | None = Field(description="Current canonical rendering; null if the term is not named yet.")


class ConventionsContext(AgentModel):
    """What the conventions agent sees before it calls tools."""

    start_chapter_num: int | None = Field(description="First reviewed chapter; null means the first chapter.")
    end_chapter_num: int = Field(description="Last reviewed chapter.")
    conventions: list[ContextConvention]
    terms: list[ContextTerm] = Field(
        description="Terms in the reviewed chapters, grouped by kind and earliest first within each kind."
    )
    terms_truncated: bool = Field(description="Whether more terms occur in the range than are listed.")


def _shorten(text: str) -> str:
    return text if len(text) <= MAX_DEFINITION_CHARS else text[: MAX_DEFINITION_CHARS - 1] + "…"


def conventions_context(deps: MemAgentDeps, start_chapter_num: int | None) -> ConventionsContext:
    """Build the conventions agent's context and register its convention handles.

    Args:
        deps: Run dependencies; listed conventions get handles in ``deps.convention_handles``.
        start_chapter_num: First reviewed chapter (inclusive), or None for the first chapter. The last
            reviewed chapter is the access context's chapter.

    Returns:
        The group's naming conventions and up to ``MAX_CONTEXT_TERMS`` terms from the reviewed chapters.
    """
    db, ctx = deps.db, deps.mem_access_context
    end_chapter_num, _ = check_mem_access_ctx(db, ctx)
    conventions = [
        ContextConvention(
            handle=deps.convention_handles.new(row.convention_id),
            title=row.title,
            rule=row.rule,
            rationale=row.rationale,
            review_status=row.review_status,
            editable=row.creator_type == Creator.AGENT and row.review_status == ReviewStatus.PENDING,
        )
        for row in read_conventions(db, ctx.memory_group_id, category=ConventionCategory.NAMING)
    ]
    range_terms, terms_truncated = glossary.get_terms_in_chapter_range(
        db, ctx, start_chapter_num, limit=MAX_CONTEXT_TERMS
    )
    range_terms.sort(key=lambda row: (row.term.term_kind or "", row.first_chapter_num, row.term.term))
    terms = [row.term for row in range_terms]
    # Newest first; a term normally has one active definition, so a page of twice the terms covers them.
    definition_page = glossary.inspect_terms(
        db, ctx, [term.term for term in terms], [MemoryType.DEFINITION], limit=2 * len(terms)
    )
    definitions: dict[str, str] = {}
    for row in definition_page.rows:
        for associated in row.terms:
            definitions.setdefault(associated.term, row.memory.memory_content)
    translations = {
        mapping.term: mapping.translation for mapping in read_term_translations(db, ctx, [term.term for term in terms])
    }
    return ConventionsContext(
        start_chapter_num=start_chapter_num,
        end_chapter_num=end_chapter_num,
        conventions=conventions,
        terms=[
            ContextTerm(
                term=row.term.term,
                kind=row.term.term_kind,
                first_chapter_num=row.first_chapter_num,
                definition=_shorten(definitions[row.term.term]) if row.term.term in definitions else None,
                translation=translations.get(row.term.term),
            )
            for row in range_terms
        ],
        terms_truncated=terms_truncated,
    )
