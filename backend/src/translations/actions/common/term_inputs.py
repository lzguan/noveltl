from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.plugins.glossary.models import GlossaryTerm
from src.memory.plugins.translations.models import TermTranslation
from src.memory.types import ReviewStatus


async def read_term_translation_map(db: AsyncSession, memory_group_id: UUID) -> dict[str, str]:
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
    return {term: translation for term, translation in await db.execute(statement)}
