"""
Database model for languages.
"""

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..models import Base
from .constants import MAX_LANGUAGE_CODE_LENGTH, MAX_LANGUAGE_NAME_LENGTH

if TYPE_CHECKING:
    from ..novels.models import Novel


class Language(Base):
    """
    Database model for a language.

    Attributes:
        language_name: Name of language. For example, English, French, Chinese. These are unique in the database.
        language_code: An ISO 639-1 language code identifier for the corresponding language. These are unique in the database.
    """
    __tablename__ = 'languages'

    language_name : Mapped[str] = mapped_column(String(MAX_LANGUAGE_NAME_LENGTH), nullable=False)
    language_code: Mapped[str] = mapped_column(String(MAX_LANGUAGE_CODE_LENGTH), primary_key=True)

    novels_with_language : Mapped[list["Novel"]] = relationship(back_populates="language_of_novel", passive_deletes=True)

    __table_args__ = (
        CheckConstraint('char_length(language_code) = 2', name='chk_language_code_length'),
        UniqueConstraint('language_name', name='language_name_unique'),
    )

