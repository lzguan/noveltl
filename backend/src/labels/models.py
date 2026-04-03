"""
Database models for labels.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Enum, Float, ForeignKey, Integer, String, UniqueConstraint, and_, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..models import Base
from .constants import MAX_LABEL_ENTITY_GROUP_NAME_LEN, MAX_LABEL_GROUP_NAME_LEN, MAX_LABEL_WORD_LEN, LabelRole

if TYPE_CHECKING:
    from src.auth.models import User
    from src.novels.models import Novel, RevisionText


class LabelGroup(Base):
    """
    Class for grouping labels for each chapter for a given novel and user

    Attributes:
        label_group_id: Integer identifier.
        label_group_name: Name given to this label group.
        novel_id: Novel this label group is referring to.
    """

    __tablename__ = "label_groups"
    label_group_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    label_group_name: Mapped[str] = mapped_column(String(MAX_LABEL_GROUP_NAME_LEN))

    novel_id = mapped_column(ForeignKey("novels.novel_id", name="fk_label_groups_novel_id_novels"), nullable=False)
    novel_of_label_group: Mapped["Novel"] = relationship(back_populates="label_groups_with_novel")

    label_datas_with_label_group: Mapped[list["LabelData"]] = relationship(
        back_populates="label_group_of_label_data", cascade="all, delete-orphan"
    )
    label_contributors_with_label_group: Mapped[list["LabelContributor"]] = relationship(
        back_populates="label_group_of_label_contributor", cascade="all, delete-orphan"
    )


class LabelContributor(Base):
    """
    Association table for many-to-many relationship between LabelGroup and Users.

    Attributes:
        label_contributor_role: Role of the user in the label group (e.g., 'owner', 'contributor').
        label_group_id: Foreign key identifier for the LabelGroup.
        user_id: Foreign key identifier for the User.
    """

    __tablename__ = "label_group_contributors"

    label_contributor_role: Mapped[LabelRole] = mapped_column(
        Enum(LabelRole, native_enum=False, length=10, values_callable=lambda x: [str(e.value) for e in x]),
        nullable=False,
    )  # type: ignore

    label_group_id = mapped_column(ForeignKey("label_groups.label_group_id"), primary_key=True)
    label_group_of_label_contributor: Mapped[LabelGroup] = relationship(
        back_populates="label_contributors_with_label_group"
    )

    user_id = mapped_column(ForeignKey("users.user_id"), primary_key=True)
    user_of_label_contributor: Mapped["User"] = relationship(back_populates="label_contributors_with_user")


class LabelData(Base):
    """
    Class for storing label data for a given chapter.

    Attributes:
        label_data_id: Integer identifier.
        label_group_id: Label group that label_data belongs to.
        revision_text_id: UUID of chapter revision text this label data corresponds to.

    Note:
        Each label group can only have 1 label data corresponding to a given chapter.

    """

    __tablename__ = "label_datas"

    label_data_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID, primary_key=True, server_default=func.gen_random_uuid()
    )

    label_group_id = mapped_column(
        ForeignKey("label_groups.label_group_id", name="fk_label_datas_label_group_id_label_groups"), nullable=False
    )
    label_group_of_label_data: Mapped[LabelGroup] = relationship(back_populates="label_datas_with_label_group")

    revision_text_id = mapped_column(
        ForeignKey("revision_texts.revision_text_id", name="fk_label_datas_revision_text_id_revision_texts"),
        nullable=False,
    )
    revision_text_of_label_data: Mapped["RevisionText"] = relationship(back_populates="label_datas_with_revision_text")

    labels_with_label_data: Mapped[list["Label"]] = relationship(
        back_populates="label_data_of_label", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("label_group_id", "revision_text_id", name="one_label_group_per_chapter"),)


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

    __tablename__ = "labels"

    label_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    label_entity_group: Mapped[str] = mapped_column(
        String(MAX_LABEL_ENTITY_GROUP_NAME_LEN), default="MISC", nullable=False
    )
    label_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    label_word: Mapped[str] = mapped_column(String(MAX_LABEL_WORD_LEN), nullable=False)
    label_start: Mapped[int] = mapped_column(Integer, nullable=False)
    label_end: Mapped[int] = mapped_column(Integer, nullable=False)
    label_dirty: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    label_data_id = mapped_column(
        ForeignKey("label_datas.label_data_id", name="fk_labels_label_data_id_label_datas"), nullable=False
    )
    label_data_of_label: Mapped["LabelData"] = relationship(back_populates="labels_with_label_data")

    __table_args__ = (
        CheckConstraint(and_(label_score >= 0.0, label_score <= 1.0), name="chk_score_bounds"),
        CheckConstraint(label_start < label_end, name="chk_label_start_lt_label_end"),
        ExcludeConstraint(
            (label_data_id, "="),
            (func.int4range(label_start, label_end, "[)"), "&&"),
            name="no_overlapping_labels_per_group",
            using="gist",
        ),
    )
