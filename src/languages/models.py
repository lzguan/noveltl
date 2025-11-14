"""
Database model for languages.
"""

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column, relationship
from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from typing import List
from .constants import *
from ..models import Base

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
    language_name : Mapped[str] = mapped_column(String(31), nullable=False)
    language_code: Mapped[str] = mapped_column(String(2), nullable=False)

    novels_with_language : Mapped[List["Novel"]] = relationship(back_populates="language_of_novel")
    translations_with_language : Mapped[List["Translation"]] = relationship(back_populates='language_of_translation')

    __table_args__ = (
        UniqueConstraint('language_name', name='language_name_unique'),
        UniqueConstraint('language_code', name='language_code_unique')
    )
