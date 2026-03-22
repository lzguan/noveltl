"""
Database models for novels and chapters.
"""

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Dialect,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    not_,
    or_,
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

    novel_parent : Mapped["Novel"] = relationship("Novel", back_populates="novel_children", remote_side=[novel_id])
    novel_children : Mapped[list["Novel"]] = relationship("Novel", back_populates="novel_parent")

    language_code : Mapped[str] = mapped_column(ForeignKey("languages.language_code", name='fk_novels_language_code_languages'), nullable=False)
    language_of_novel : Mapped["Language"] = relationship(back_populates="novels_with_language")

    chapters_with_novel : Mapped[list["Chapter"]] = relationship(back_populates='novel_of_chapter')
    label_groups_with_novel : Mapped[list["LabelGroup"]] = relationship(back_populates='novel_of_label_group')
    contributors_with_novel : Mapped[list["Contributor"]] = relationship(back_populates='novel_of_contributor')

class Contributor(Base):
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
    novel_of_contributor : Mapped["Novel"] = relationship(back_populates='contributors_with_novel')

    user_id = mapped_column(ForeignKey('users.user_id'), primary_key=True)
    user_of_contributor : Mapped["User"] = relationship(back_populates='contributors_with_user')


class Chapter(Base):
    """
    Database model for metadata for a specific chapter number in the novel.

    Attributes:
        chapter_id: Integer primary key identifier.
        chapter_num: Integer chapter numbering. For example, a value of 5 would correspond to chapter 5.
        novel_id: Integer foreign key identifier to the novel this chapter belongs to.

    Note:
        Each pair (chapter_num, novel_id) should be unique.
        chapter_num and novel_id are non-nullable.
    """
    __tablename__ = 'chapters'

    chapter_id : Mapped[uuid.UUID] = mapped_column(postgresql.UUID, primary_key=True, server_default=func.gen_random_uuid())
    chapter_num : Mapped[int] = mapped_column(Integer, nullable=False)

    novel_id = mapped_column(ForeignKey('novels.novel_id', name='fk_chapters_novel_id_novels'), nullable=False)
    novel_of_chapter : Mapped[Novel] = relationship(back_populates='chapters_with_novel')

    revisions_with_chapter : Mapped[list["Revision"]] = relationship(back_populates='chapter_of_revision')

    __table_args__ = (
        UniqueConstraint('chapter_num', 'novel_id', name="chapter_per_novel"),
    )

class Revision(Base):
    """
    Database model for a revision of a chapter of a novel. Each revision corresponds to a Chapter and contains the text of that chapter for a specific revision. Once a revision is flagged as public, the revision should no longer be able to be made private or modified.

    Attributes:
        revision_id: Integer primary key identifier.
        revision_title: Chapter title. Different revisions of the same chapter can have different titles.
        revision_is_primary: Boolean mark for whether a revision is the primary chapter (the 'finalized' chapter)
        revision_is_public: Boolean mark for whether a revision is marked as public.
        chapter_id: Id of chapter this revision belongs to.

    Note:
        revision_title must have length at most MAX_CHAPTER_TITLE_LEN.
        Both public and primary flags are non-nullable.
        chapter_id is non-nullable.
        For each chapter_id, only one Revision can be marked as primary.
        If a Revision is marked as primary, it must be marked as public.
    """
    __tablename__ = 'revisions'

    revision_id : Mapped[uuid.UUID] = mapped_column(postgresql.UUID, primary_key=True, server_default=func.gen_random_uuid())
    revision_title : Mapped[str] = mapped_column(String(MAX_CHAPTER_TITLE_LEN))
    revision_is_primary : Mapped[bool] = mapped_column(Boolean, nullable=False)
    revision_is_public : Mapped[bool] = mapped_column(Boolean, nullable=False)

    chapter_of_revision : Mapped["Chapter"] = relationship(back_populates="revisions_with_chapter")
    chapter_id = mapped_column(ForeignKey('chapters.chapter_id', name='fk_revisions_chapter_id_chapters'), nullable=False)

    revision_texts_with_revision : Mapped[list["RevisionText"]] = relationship(back_populates='revision_of_revision_text', cascade='all, delete-orphan')

    __table_args__ = (
        Index('ix_one_primary_revision_per_chapter', 'chapter_id', unique=True, postgresql_where=revision_is_primary.is_(True)),
        CheckConstraint(or_(revision_is_public, not_(revision_is_primary)), name="primary_must_be_public_check")
    )

class RevisionText(Base):
    """
    Database model for the text of a specific revision. RevisionText are versioned separately from the metadata of a revision (for example, whether it is public or primary) since we want to be able to update the metadata of a revision without modifying the text, and we want to be able to store the text in a separate table for organizational purposes.

    Attributes:
        revision_text_uuid: UUID for the revision text, used for uniquely identifying a specific revision text across different versions. For each revision_id, the pair (revision_id, revision_text_uuid) should be unique.
        revision_text_content: Text content of the revision.
        revision_text_version: Integer version number for the revision text. For each revision_id, the pair (revision_id, revision_text_version) should be unique.

        revision_id: Integer foreign key identifier to the revision this text corresponds to.
    """
    __tablename__ = 'revision_texts'

    revision_text_id : Mapped[uuid.UUID] = mapped_column(postgresql.UUID, primary_key=True, server_default=func.gen_random_uuid())
    revision_text_content : Mapped[str] = mapped_column(Text, nullable=False)
    revision_text_version : Mapped[int] = mapped_column(Integer, nullable=False)

    revision_of_revision_text : Mapped["Revision"] = relationship(back_populates="revision_texts_with_revision")
    revision_id = mapped_column(ForeignKey('revisions.revision_id', name='fk_revision_texts_revision_id_revisions'), nullable=False)

    label_datas_with_revision_text : Mapped[list["LabelData"]] = relationship(back_populates='revision_text_of_label_data')

    auto_labels_with_revision_text : Mapped[list["AutoLabel"]] = relationship(back_populates='revision_text_of_auto_label', cascade='all, delete-orphan')

    __table_args__ = (
        UniqueConstraint('revision_id', 'revision_text_version', name="uq_revision_text_version_per_revision"),
    )
