"""
Database models for labels.
"""

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column, relationship
from sqlalchemy import String, Float, Integer, Boolean, ForeignKey, UniqueConstraint, CheckConstraint, func, and_
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from typing import List, TYPE_CHECKING
from .constants import *
from ..models import Base

if TYPE_CHECKING:
    from src.novels.models import Novel, RawChapterRevision
    from src.auth.models import User

class LabelGroup(Base):
    """
    Class for grouping labels for each chapter for a given novel and user
    
    Attributes:
        label_group_id: Integer identifier.
        label_group_name: Name given to this label group.
        user_id: User that owns this label group.
        novel_id: Novel this label group is referring to.
    
    Note:
        Each user can only have one label group with a given name per novel.
    """
    __tablename__ = 'label_groups'
    label_group_id : Mapped[int] = mapped_column(primary_key=True)
    label_group_name : Mapped[str] = mapped_column(String(MAX_LABEL_GROUP_NAME_LEN))
    
    user_id : Mapped[int] = mapped_column(ForeignKey('users.user_id'), nullable=False)
    user_of_label_group : Mapped["User"] = relationship(back_populates='label_groups_with_user')

    novel_id : Mapped[int] = mapped_column(ForeignKey('novels.novel_id'), nullable=False)
    novel_of_label_group : Mapped["Novel"] = relationship(back_populates='label_groups_with_novel')

    label_datas_with_label_group : Mapped[List["LabelData"]] = relationship(back_populates='label_group_of_label_data', cascade='all, delete-orphan')

    __table_args__ = (
        UniqueConstraint('label_group_name', 'user_id', 'novel_id', name="one_label_group_with_name_per_user_novel"),
    )

class LabelData(Base):
    """
    Class for storing label data for a given chapter.
    
    Attributes:
        label_data_id: Integer identifier.
        label_group_id: Label group that label_data belongs to.
        raw_chapter_revision_id: id of chapter revision this label data corresponds to.

    Note:
        Each label group can only have 1 label data corresponding to a given chapter.

    """
    __tablename__ = 'label_datas'

    label_data_id : Mapped[int] = mapped_column(primary_key=True)

    label_group_id : Mapped[int] = mapped_column(ForeignKey('label_groups.label_group_id'), nullable=False)
    label_group_of_label_data : Mapped[LabelGroup] = relationship(back_populates='label_datas_with_label_group')

    raw_chapter_revision_id : Mapped[int] = mapped_column(ForeignKey('raw_chapter_revisions.raw_chapter_revision_id'), nullable=False)
    raw_chapter_revision_of_label_data : Mapped["RawChapterRevision"] = relationship(back_populates='label_datas_with_raw_chapter_revision')

    labels_with_label_data : Mapped[List["Label"]] = relationship(back_populates='label_data_of_label', cascade='all, delete-orphan')

    __table_args__ = (
        UniqueConstraint('label_group_id', 'raw_chapter_revision_id', name='one_label_group_per_chapter'),
    )

class Label(Base):
    """
    Database model for a single labeled entity (e.g. a name, location, or term) within a specific text range.

    Attributes:
        label_id: Integer primary key identifier.
        label_entity_group: The category of the entity (e.g., 'PER', 'LOC', 'ORG', 'TECHNIQUE').
        label_score: Confidence score of the label, between 0.0 and 1.0. Defaults to 1.0.
        label_word: The exact text content of the label. Max length 128 characters.
        label_start: The starting character index of the label in the text (inclusive).
        label_end: The ending character index of the label in the text (exclusive).
        label_dirty: Boolean flag indicating if the label has been manually edited/verified (True) or is raw AI output (False).
        label_data_id: Foreign key identifier for the parent LabelData group.

    Note:
        Constraints ensure that `label_start` < `label_end`.
        Constraints ensure `label_score` is between 0.0 and 1.0.
        An Exclusion Constraint ensures no two labels within the same `label_data_id` can have overlapping text ranges.
    """
    __tablename__ = 'labels'

    label_id : Mapped[int] = mapped_column(primary_key=True)
    label_entity_group : Mapped[str] = mapped_column(String(MAX_LABEL_ENTITY_GROUP_NAME_LEN), default="MISC", nullable=False)
    label_score : Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    label_word : Mapped[str] = mapped_column(String(MAX_LABEL_WORD_LEN), nullable=False)
    label_start : Mapped[int] = mapped_column(Integer, nullable=False)
    label_end : Mapped[int] = mapped_column(Integer, nullable=False)
    label_dirty : Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    label_data_id : Mapped[int] = mapped_column(ForeignKey('label_datas.label_data_id'), nullable=False)
    label_data_of_label : Mapped["LabelData"] = relationship(back_populates='labels_with_label_data')

    __table_args__ = (
        UniqueConstraint(label_start, label_data_id, name='uq_one_label_with_start_per_label_data'),
        CheckConstraint(and_(label_score >= 0.0, label_score <= 1.0), name='chk_score_bounds'),
        CheckConstraint(label_start < label_end, name="chk_label_start_lt_label_end"),
        ExcludeConstraint(
            (label_data_id, '='),
            (func.int4range(label_start, label_end, '[)'), '&&'),
            name='no_overlapping_labels_per_group',
            using='gist'
        )
    )
