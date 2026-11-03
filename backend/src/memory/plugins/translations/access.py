"""Shared canonical term-translation access for naming and chapter preparation."""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.memory.access import MemAccessContext, check_mem_access_ctx
from src.memory.exceptions import GlossaryTermNotFoundException
from src.memory.plugins.glossary.models import GlossaryTerm
from src.memory.plugins.translations.models import TermTranslation as TermTranslationRow
from src.memory.plugins.translations.schemas import TermTranslation
from src.memory.types import Creator, ReviewStatus


def read_term_translations(db: Session, ctx: MemAccessContext, term_names: Sequence[str]) -> list[TermTranslation]:
    """Read usable exact-form mappings; the term key guarantees uniqueness."""
    if not term_names:
        return []
    check_mem_access_ctx(db, ctx)
    statement = (
        select(GlossaryTerm.term, TermTranslationRow.translation, TermTranslationRow.review_status)
        .join(TermTranslationRow, TermTranslationRow.term_id == GlossaryTerm.term_id)
        .where(
            GlossaryTerm.memory_group_id == ctx.memory_group_id,
            GlossaryTerm.term.in_(term_names),
            GlossaryTerm.review_status != ReviewStatus.REJECTED,
            TermTranslationRow.review_status != ReviewStatus.REJECTED,
        )
        .order_by(GlossaryTerm.term)
    )
    return [TermTranslation.model_validate(row) for row in db.execute(statement).mappings()]


def missing_term_translations(db: Session, ctx: MemAccessContext, term_names: Sequence[str]) -> list[str]:
    existing = {mapping.term for mapping in read_term_translations(db, ctx, term_names)}
    return list(dict.fromkeys(term for term in term_names if term not in existing))


def create_term_translation(db: Session, ctx: MemAccessContext, term: str, translation: str) -> None:
    """Fill a missing/rejected mapping atomically, preserving every usable choice.

    A rejected mapping becomes a new pending agent suggestion. The caller owns
    the transaction, so publication still commits with naming-stage completion.
    """
    if not translation.strip():
        raise ValueError("A term translation must not be blank")
    check_mem_access_ctx(db, ctx)
    term_id = db.scalar(
        select(GlossaryTerm.term_id).where(
            GlossaryTerm.memory_group_id == ctx.memory_group_id,
            GlossaryTerm.term == term,
            GlossaryTerm.review_status != ReviewStatus.REJECTED,
        )
    )
    if term_id is None:
        raise GlossaryTermNotFoundException(f"No usable glossary term {term!r} in this memory group")
    statement = insert(TermTranslationRow).values(
        term_id=term_id, translation=translation.strip(), review_status=ReviewStatus.PENDING, creator_type=Creator.AGENT
    )
    db.execute(
        statement.on_conflict_do_update(
            index_elements=[TermTranslationRow.term_id],
            set_={
                "translation": statement.excluded.translation,
                "review_status": ReviewStatus.PENDING,
                "creator_type": Creator.AGENT,
                "updated_at": func.now(),
            },
            where=TermTranslationRow.review_status == ReviewStatus.REJECTED,
        )
    )
