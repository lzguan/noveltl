"""Naming context preparation and read-only translation tools."""

from typing import Annotated

from pydantic import Field
from pydantic_ai import FunctionToolset, RunContext
from sqlalchemy.orm import Session

from src.memory.access import MemAccessContext
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.plugins.conventions.access import read_conventions
from src.memory.plugins.conventions.schemas import AgentConvention
from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.plugins.glossary import access
from src.memory.plugins.glossary.schemas import AgentGlossaryMemoryPage
from src.memory.plugins.glossary.types import TermKind
from src.memory.plugins.translations.access import missing_term_translations, read_term_translations
from src.memory.plugins.translations.schemas import TermTranslation
from src.memory.types import MemoryType, ReviewStatus
from src.schemas import Model


class RequestedTerm(Model):
    term: str
    kind: TermKind | None


class TermTranslationContext(Model):
    requested_terms: list[RequestedTerm]
    established_translations: list[TermTranslation]
    memories_and_aliases: AgentGlossaryMemoryPage
    # None when the stage does not use conventions, so the prompt omits the key.
    conventions: list[AgentConvention] | None = None


def term_translations(
    ctx: RunContext[MemAgentDeps], term_names: Annotated[list[str], Field(min_length=1, max_length=50)]
) -> list[TermTranslation]:
    """Retrieve usable canonical renderings for exact source forms in this group."""
    return read_term_translations(ctx.deps.db, ctx.deps.mem_access_context, term_names)


def term_translation_context(
    db: Session, ctx: MemAccessContext, *, include_conventions: bool = False
) -> TermTranslationContext | None:
    """Prepare a bounded naming context from this chapter and its known aliases."""
    terms = access.get_terms_in_chapter(db, ctx, access.contains_query)
    names = [term.term for term in terms]
    missing = missing_term_translations(db, ctx, names)
    if not missing:
        return None
    context = access.inspect_terms(
        db, ctx, missing, [MemoryType.DEFINITION, MemoryType.RELATION], limit=100, expand_aliases=True
    )
    # The expanded result exposes the actual alias links as well as retrieved
    # memories. Source forms remain distinct throughout naming and persistence.
    if not isinstance(context, AgentGlossaryMemoryPage):
        raise RuntimeError("Naming context requires alias-aware retrieval")
    related_names = set(names)
    for alias in context.aliases:
        related_names.update(term.term for term in alias.terms)
    return TermTranslationContext(
        requested_terms=[RequestedTerm(term=term.term, kind=term.term_kind) for term in terms if term.term in missing],
        established_translations=read_term_translations(db, ctx, sorted(related_names)),
        memories_and_aliases=context,
        conventions=[
            AgentConvention.model_validate(row)
            for row in read_conventions(
                db,
                ctx.memory_group_id,
                workspace_id=ctx.workspace_id,
                category=ConventionCategory.NAMING,
                review_statuses=[ReviewStatus.PENDING, ReviewStatus.APPROVED],
            )
        ]
        if include_conventions
        else None,
    )


translations_read_toolset = FunctionToolset(tools=[term_translations], sequential=True)
