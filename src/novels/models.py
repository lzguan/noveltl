"""
Database models for novels and chapters.
"""

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column, relationship
from sqlalchemy import String, UniqueConstraint, ForeignKey, Integer, Text, Boolean, Index, CheckConstraint, or_, not_
from typing import List
from .constants import *
from ..models import Base

class Novel(Base):
    """
    Database model for novel.

    Attributes:
        novel_id: Integer primary key identifier.
        novel_title: Title of novel.
        novel_description: Description/summary of novel.
        novel_author: Author of novel.
        language_id: Integer foreign key for the language the novel is written in.
    
    Note:
        novel_title is non-nullable.
        novel_author must have length at most MAX_AUTHOR_LENGTH.
    """
    __tablename__ = "novels"

    novel_id : Mapped[int] = mapped_column(primary_key=True)
    novel_title : Mapped[str] = mapped_column(String(MAX_NOVEL_TITLE_LEN), nullable=False)
    novel_description : Mapped[str] = mapped_column(Text)
    novel_author : Mapped[str] = mapped_column(String(MAX_AUTHOR_LENGTH))

    language_id = mapped_column(ForeignKey("languages.language_id"), nullable=False)
    language_of_novel : Mapped["Language"] = relationship(back_populates="novels_with_language")

    raw_chapters_with_novel : Mapped[List["RawChapter"]] = relationship(back_populates='novel_of_raw_chapter')
    translations_with_novel : Mapped[List["Translation"]] = relationship(back_populates='novel_of_translation')
    label_groups_with_novel : Mapped[List["LabelGroup"]] = relationship(back_populates='novel_of_label_group')

class RawChapter(Base):
    """
    Database model for metadata for a specific chapter number in the novel.

    Attributes:
        raw_chapter_id: Integer primary key identifier.
        raw_chapter_num: Integer chapter numbering. For example, a value of 5 would correspond to chapter 5.
        novel_id: Integer foreign key identifier to the novel this chapter belongs to.
    
    Note:
        Each pair (raw_chapter_num, novel_id) should be unique.
        raw_chapter_num and novel_id are non-nullable.
    """
    __tablename__ = 'raw_chapters'

    raw_chapter_id : Mapped[int] = mapped_column(primary_key=True)
    raw_chapter_num : Mapped[int] = mapped_column(Integer, nullable=False)

    novel_id = mapped_column(ForeignKey('novels.novel_id'), nullable=False)
    novel_of_raw_chapter : Mapped[Novel] = relationship(back_populates='raw_chapters_with_novel')

    translated_chapters_with_raw_chapter : Mapped[List["TranslatedChapter"]] = relationship(back_populates='raw_chapter_of_translated_chapter')

    raw_chapter_revisions_with_raw_chapter : Mapped[List["RawChapterRevision"]] = relationship(back_populates='raw_chapter_of_raw_chapter_revision')

    __table_args__ = (
        UniqueConstraint('raw_chapter_num', 'novel_id', name="raw_chapter_per_novel"),
    )

class RawChapterRevision(Base):
    """
    Database model for a revision of a chapter of a novel. Each revision corresponds to a RawChapter and contains the text of that chapter for a specific revision. Once a revision is flagged as public, the revision should no longer be able to be made private or modified.

    Attributes:
        raw_chapter_revision_id: Integer primary key identifier.
        raw_chapter_revision_text: Text contained in this revision of the chapter.
        raw_chapter_revision_title: Chapter title. Different revisions of the same chapter can have different titles.
        raw_chapter_revision_is_primary: Boolean mark for whether a chapter is the primary chapter (the 'finalized' chapter)
        raw_chapter_revision_is_public: Boolean mark for whether a chapter is marked as public. Chapters marked as public should be immutable and available for use in other modules.
    
    Note:
        raw_chapter_revision_title must have length at most MAX_CHAPTER_TITLE_LEN.
        Both public and primary flags are non-nullable.
        raw_chapter_id is non-nullable.
        For each raw_chapter_id, only one RawChapterRevision can be marked as primary.
        If a RawChapterRevision is marked as primary, it must be marked as public.
    """
    __tablename__ = 'raw_chapter_revisions'

    raw_chapter_revision_id : Mapped[int] = mapped_column(primary_key=True)
    raw_chapter_revision_text : Mapped[str] = mapped_column(Text)
    raw_chapter_revision_title : Mapped[str] = mapped_column(String(MAX_CHAPTER_TITLE_LEN))
    raw_chapter_revision_is_primary : Mapped[bool] = mapped_column(Boolean, nullable=False)
    raw_chapter_revision_is_public : Mapped[bool] = mapped_column(Boolean, nullable=False)

    raw_chapter_of_raw_chapter_revision : Mapped["RawChapter"] = relationship(back_populates="raw_chapter_revisions_with_raw_chapter")
    raw_chapter_id = mapped_column(ForeignKey('raw_chapters.raw_chapter_id'), nullable=False)

    label_datas_with_raw_chapter_revision : Mapped[List["LabelData"]] = relationship(back_populates='raw_chapter_revision_of_label_data')

    __table_args__ = (
        Index('ix_one_primary_revision_per_chapter', 'raw_chapter_id', unique=True, postgresql_where=(raw_chapter_revision_is_primary.is_(True))),
        CheckConstraint(or_(raw_chapter_revision_is_public, not_(raw_chapter_revision_is_primary)), name="primary_must_be_public_check")
    )