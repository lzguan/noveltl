from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.memory.plugins.glossary.models import GlossaryTerm
from src.memory.plugins.translations.models import TermTranslation
from src.memory.types import ReviewStatus


def read_term_translation_map(db: Session, memory_group_id: UUID) -> dict[str, str]:
    statement = (
        select(GlossaryTerm.term, TermTranslation.translation)
        .join(TermTranslation, TermTranslation.term_id == GlossaryTerm.term_id)
        .where(
            GlossaryTerm.memory_group_id == memory_group_id,
            GlossaryTerm.review_status != ReviewStatus.REJECTED,
            TermTranslation.review_status != ReviewStatus.REJECTED,
        )
        .order_by(GlossaryTerm.term)
    )
    return {term: translation for term, translation in db.execute(statement)}
