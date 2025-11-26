"""
Database model for languages.
"""

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column, relationship
from sqlalchemy import String, UniqueConstraint, CheckConstraint
from typing import List, TYPE_CHECKING
from .constants import *
from ..models import Base

if TYPE_CHECKING:
    from src.novels.models import Novel
    from src.translations.models import Translation

class Language(Base):
    """
    Database model for a language.

    Attributes:
        language_id: Identifier.
        language_name: Name of language. For example, English, French, Chinese. These are unique in the database.
        language_code: An ISO 639-1 language code identifier for the corresponding language. These are unique in the database.
    """
    __tablename__ = 'languages'

    language_id : Mapped[int] = mapped_column(primary_key=True)
    language_name : Mapped[str] = mapped_column(String(MAX_LANGUAGE_NAME_LENGTH), nullable=False)
    language_code: Mapped[str] = mapped_column(String(MAX_LANGUAGE_CODE_LENGTH), nullable=False)

    novels_with_language : Mapped[List["Novel"]] = relationship(back_populates="language_of_novel", passive_deletes=True)
    translations_with_language : Mapped[List["Translation"]] = relationship(back_populates='language_of_translation')

    __table_args__ = (
        CheckConstraint('char_length(language_code) = 2', name='chk_language_code_length'),
        UniqueConstraint('language_name', name='language_name_unique'),
        UniqueConstraint('language_code', name='language_code_unique')
    )

