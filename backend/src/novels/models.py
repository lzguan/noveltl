"""
Database models for novels and chapters.
"""

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    Dialect,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from ..models import Base
from .constants import MAX_AUTHOR_LENGTH, MAX_CHAPTER_TITLE_LEN, MAX_NOVEL_TITLE_LEN, NovelType, Role, Visibility

if TYPE_CHECKING:
    from src.auth.models import User
    from src.autolabels.models import AutoLabel
    from src.labels.models import LabelData, LabelGroup
    from src.languages.models import Language

class EnumAsInteger(TypeDecorator): # type: ignore
    """
    Custom SQLAlchemy type to store Python Enums as integers in the database.

    Copied off stackoverflow.
    https://stackoverflow.com/questions/32287299/sqlalchemy-database-int-to-python-enum
    """
    impl = Integer
    cache_ok = True

    def __init__(self, enum_type): # type: ignore
        super().__init__()
        self.enum_type = enum_type

    def process_bind_param(self, value: Any | None, dialect: Dialect) -> Any:
        if value is not None and isinstance(value, self.enum_type):
            return value.value
        raise ValueError(f"Invalid value {value} for enum {self.enum_type}")

    def process_result_value(self, value: Any | None, dialect: Dialect) -> Any | None:
        return self.enum_type(value) # type: ignore

    def copy(self, **kwargs): # type: ignore
        return EnumAsInteger(self.enum_type) # type: ignore

class SourceWork(Base):
    """
    Database model to track the source work for a novel, for example if the novel is a translation of another novel.
    """
    __tablename__ = 'source_works'

    source_work_id : Mapped[uuid.UUID] = mapped_column(postgresql.UUID, primary_key=True, server_default=func.gen_random_uuid())
    source_work_title : Mapped[str] = mapped_column(String(MAX_NOVEL_TITLE_LEN), nullable=False)
    source_work_description : Mapped[str] = mapped_column(Text, nullable=True)

    novels_with_source_work : Mapped[list["Novel"]] = relationship(back_populates='source_work_of_novel')

class Novel(Base):
    """
    Database model for novel.

    Attributes:
        novel_id: Integer primary key identifier.
        novel_title: Title of novel.
        novel_description: Description/summary of novel.
        novel_author: Author of novel.
        novel_visibility: Visibility level of novel. Encoded as a Visibility enum.
        novel_type: Type of novel. Encoded as a NovelType enum.
        novel_parent_id: Integer foreign key identifier to parent novel, for example if this novel is a translation of another novel.
        language_code: String foreign key for the language the novel is written in.
        source_work_id: Integer foreign key identifier to the source work for this novel.

    Note:
        novel_title is non-nullable.
        novel_author must have length at most MAX_AUTHOR_LENGTH.
    """
    __tablename__ = "novels"

    novel_id : Mapped[uuid.UUID] = mapped_column(postgresql.UUID, primary_key=True, server_default=func.gen_random_uuid())
    novel_title : Mapped[str] = mapped_column(String(MAX_NOVEL_TITLE_LEN), nullable=False)
    novel_description : Mapped[str] = mapped_column(Text, nullable=True)
    novel_author : Mapped[str] = mapped_column(String(MAX_AUTHOR_LENGTH), nullable=True)
    novel_visibility : Mapped[Visibility] = mapped_column(EnumAsInteger(Visibility), nullable=False)
    novel_type : Mapped[NovelType] = mapped_column(Enum(NovelType, native_enum=False, length=16, values_callable=lambda x : [str(e.value) for e in x]), nullable=False) # type: ignore

    source_work_id : Mapped[uuid.UUID] = mapped_column(ForeignKey("source_works.source_work_id"), nullable=False)
    source_work_of_novel : Mapped["SourceWork"] = relationship(back_populates="novels_with_source_work")

    language_code : Mapped[str] = mapped_column(ForeignKey("languages.language_code", name='fk_novels_language_code_languages'), nullable=False)
    language_of_novel : Mapped["Language"] = relationship(back_populates="novels_with_language")

    chapters_with_novel : Mapped[list["Chapter"]] = relationship(back_populates='novel_of_chapter')
    label_groups_with_novel : Mapped[list["LabelGroup"]] = relationship(back_populates='novel_of_label_group')
    novel_contributors_with_novel : Mapped[list["NovelContributor"]] = relationship(back_populates='novel_of_contributor')

class NovelContributor(Base):
    """
    Database model for a contributor to a novel. Effectively an associative array for a many-many relationship between users and novels.

    Attributes:
        contributor_id: Integer primary key identifier.
        contributor_role: Role of the contributor in the novel.
        novel_id: Integer foreign key identifier to the novel this contributor contributes to.
        user_id: Integer foreign key identifier to the user who is the contributor.
    """
    __tablename__ = 'novel_contributors'

    contributor_role : Mapped[Role] = mapped_column(Enum(Role, native_enum=False, length=10, values_callable=lambda x : [str(e.value) for e in x]), nullable=False) # type: ignore

    novel_id = mapped_column(ForeignKey('novels.novel_id'), primary_key=True)
    novel_of_contributor : Mapped["Novel"] = relationship(back_populates='novel_contributors_with_novel')

    user_id = mapped_column(ForeignKey('users.user_id'), primary_key=True)
    user_of_novel_contributor : Mapped["User"] = relationship(back_populates='novel_contributors_with_user')


class Chapter(Base):
    """
    Database model for metadata for a specific chapter number in the novel.

    Attributes:
        chapter_id: Integer primary key identifier.
        chapter_num: Integer chapter numbering. For example, a value of 5 would correspond to chapter 5.
        chapter_title: String chapter title.
        chapter_is_public: Boolean flag indicating if the chapter is public.
        novel_id: Integer foreign key identifier to the novel this chapter belongs to.

    Note:
        Each pair (chapter_num, novel_id) should be unique.
        chapter_num and novel_id are non-nullable.
    """
    __tablename__ = 'chapters'

    chapter_id : Mapped[uuid.UUID] = mapped_column(postgresql.UUID, primary_key=True, server_default=func.gen_random_uuid())
    chapter_num : Mapped[int] = mapped_column(Integer, nullable=False)
    chapter_title : Mapped[str] = mapped_column(String(MAX_CHAPTER_TITLE_LEN), nullable=True)
    chapter_is_public : Mapped[bool] = mapped_column(Boolean, nullable=False)

    novel_id = mapped_column(ForeignKey('novels.novel_id', name='fk_chapters_novel_id_novels'), nullable=False)
    novel_of_chapter : Mapped[Novel] = relationship(back_populates='chapters_with_novel')

    chapter_contents_with_chapter : Mapped[list["ChapterContent"]] = relationship(back_populates='chapter_of_chapter_content', cascade='all, delete-orphan')

    __table_args__ = (
        UniqueConstraint('chapter_num', 'novel_id', name="chapter_per_novel"),
    )

class ChapterContent(Base):
    """
    Database model for the text of a specific chapter. ChapterTextVersions are versioned separately from the metadata of a chapter (for example, whether it is public or primary) since we want to be able to update the metadata of a chapter without modifying the text, and we want to be able to store the text in a separate table for organizational purposes.

    Attributes:
        chapter_content_id: UUID primary key for the chapter content, used for uniquely identifying a specific chapter content across different versions.
        chapter_content_text: Text content of the chapter.
        chapter_content_version: Integer version number for the chapter text. For each chapter_id, the pair (chapter_id, chapter_text_version) should be unique.

        chapter_id: UUID foreign key identifier to the chapter this text corresponds to.
    """
    __tablename__ = 'chapter_contents'

    chapter_content_id : Mapped[uuid.UUID] = mapped_column(postgresql.UUID, primary_key=True, server_default=func.gen_random_uuid())
    chapter_content_text : Mapped[str] = mapped_column(Text, nullable=False)
    chapter_content_version : Mapped[int] = mapped_column(Integer, nullable=False)

    chapter_of_chapter_content : Mapped["Chapter"] = relationship(back_populates="chapter_contents_with_chapter")
    chapter_id = mapped_column(ForeignKey('chapters.chapter_id', name='fk_chapter_contents_chapter_id_chapters', ondelete='CASCADE'), nullable=False)

    label_datas_with_chapter_content : Mapped[list["LabelData"]] = relationship(back_populates='chapter_content_of_label_data')

    auto_labels_with_chapter_content : Mapped[list["AutoLabel"]] = relationship(back_populates='chapter_content_of_auto_label', cascade='all, delete-orphan')

    __table_args__ = (
        UniqueConstraint('chapter_id', 'chapter_content_version', name="uq_chapter_content_version_per_chapter"),
    )
