from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column, relationship
from sqlalchemy import UniqueConstraint, ForeignKey, Integer, Text
from typing import List, TYPE_CHECKING
from .constants import *
from ..models import Base

if TYPE_CHECKING:
    from src.languages.models import Language
    from src.novels.models import Novel, RawChapter
    from src.auth.models import User

class Translation(Base):
    __tablename__ = 'translations'

    translation_id : Mapped[int] = mapped_column(primary_key=True)

    language_of_translation : Mapped["Language"] = relationship(back_populates='translations_with_language')
    language_id = mapped_column(ForeignKey('languages.language_id'), nullable=False)

    novel_of_translation : Mapped["Novel"] = relationship(back_populates='translations_with_novel')
    novel_id = mapped_column(ForeignKey('novels.novel_id'), nullable=False)

    user_of_translation : Mapped["User"] = relationship(back_populates='translations_with_user')
    user_id = mapped_column(ForeignKey('users.user_id'), nullable=False)

    translated_chapters_with_translation : Mapped[List["TranslatedChapter"]] = relationship(back_populates='translation_of_translated_chapter')

class TranslatedChapter(Base):
    __tablename__ = 'translated_chapters'

    translated_chapter_id : Mapped[int] = mapped_column(primary_key=True)
    translated_chapter_text : Mapped[str] = mapped_column(Text)
    translated_chapter_num : Mapped[int] = mapped_column(Integer)

    translation_of_translated_chapter : Mapped[Translation] = relationship(back_populates='translated_chapters_with_translation')
    translation_id = mapped_column(ForeignKey('translations.translation_id'))

    raw_chapter_of_translated_chapter : Mapped["RawChapter"] = relationship(back_populates='translated_chapters_with_raw_chapter')
    raw_chapter_id = mapped_column(ForeignKey('raw_chapters.raw_chapter_id'))

    __table_args__ = (
        UniqueConstraint('translation_id', 'raw_chapter_id', name='tl_chapter_unique'), # todo: naming conventions? for name
    )
