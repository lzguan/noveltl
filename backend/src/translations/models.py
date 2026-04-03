"""
Database models for novel translation jobs.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..models import Base
from .constants import (
    MAX_LANGUAGE_CODE_LEN,
    MAX_MODEL_NAME_LEN,
    ChapterTranslationStatus,
    NovelTranslationStatus,
)

if TYPE_CHECKING:
    from src.glossaries.models import Glossary
    from src.novels.models import Chapter, Novel


class NovelTranslationJob(Base):
    """
    Database model for a novel translation job.

    A job translates all chapters of a source novel into a target novel
    using an optional glossary for term consistency.

    Attributes:
        job_id: UUID primary key.
        source_novel_id: FK to the novel being translated.
        target_novel_id: FK to the output novel (created by the worker). Nullable until the worker creates it.
        glossary_id: FK to the glossary used for term consistency. Optional.
        status: Current job status.
        job_model_name: LLM model used for translation.
        job_last_job_id: UUID for optimistic locking (worker claims by matching this value).
        job_message: Error or status message. Optional.
        chapters_translated: Number of chapters completed so far.
        chapters_total: Total chapters to translate.
        target_language_code: ISO 639-1 language code for the output novel.
    """

    __tablename__ = "novel_translation_jobs"

    job_id: Mapped[uuid.UUID] = mapped_column(postgresql.UUID, primary_key=True, server_default=func.gen_random_uuid())
    status: Mapped[NovelTranslationStatus] = mapped_column(
        Enum(
            NovelTranslationStatus,
            native_enum=False,
            length=10,
            values_callable=lambda x: [str(e.value) for e in x],
        ),
        nullable=False,
        default=NovelTranslationStatus.PENDING,
    )  # type: ignore
    job_model_name: Mapped[str | None] = mapped_column(String(MAX_MODEL_NAME_LEN), nullable=True)
    job_last_job_id: Mapped[uuid.UUID | None] = mapped_column(postgresql.UUID, nullable=True)
    job_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    chapters_translated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chapters_total: Mapped[int] = mapped_column(Integer, nullable=False)
    target_language_code: Mapped[str] = mapped_column(String(MAX_LANGUAGE_CODE_LEN), nullable=False)

    source_novel_id = mapped_column(
        ForeignKey(
            "novels.novel_id",
            name="fk_novel_translation_jobs_source_novel_id_novels",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    source_novel_of_job: Mapped["Novel"] = relationship(
        back_populates="source_translation_jobs_with_novel",
        foreign_keys=[source_novel_id],
    )

    target_novel_id = mapped_column(
        ForeignKey(
            "novels.novel_id",
            name="fk_novel_translation_jobs_target_novel_id_novels",
            ondelete="CASCADE",
        ),
        nullable=True,
    )
    target_novel_of_job: Mapped["Novel | None"] = relationship(
        back_populates="target_translation_jobs_with_novel",
        foreign_keys=[target_novel_id],
    )

    glossary_id = mapped_column(
        ForeignKey(
            "glossaries.glossary_id",
            name="fk_novel_translation_jobs_glossary_id_glossaries",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    glossary_of_job: Mapped["Glossary | None"] = relationship(
        back_populates="novel_translation_jobs_with_glossary",
    )

    chapter_mappings_with_job: Mapped[list["ChapterTranslationMapping"]] = relationship(
        back_populates="job_of_mapping",
        cascade="all, delete-orphan",
    )


class ChapterTranslationMapping(Base):
    """
    Database model for a per-chapter translation task within a NovelTranslationJob.

    Attributes:
        mapping_id: UUID primary key.
        job_id: FK to the parent translation job.
        source_chapter_id: FK to the chapter being translated.
        target_chapter_id: FK to the output chapter (created by the worker). Nullable until the worker creates it.
        status: Translation status for this chapter.
        mapping_message: Error or status message. Optional.
    """

    __tablename__ = "chapter_translation_mappings"

    mapping_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    status: Mapped[ChapterTranslationStatus] = mapped_column(
        Enum(
            ChapterTranslationStatus,
            native_enum=False,
            length=10,
            values_callable=lambda x: [str(e.value) for e in x],
        ),
        nullable=False,
        default=ChapterTranslationStatus.PENDING,
    )  # type: ignore
    mapping_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    job_id = mapped_column(
        ForeignKey(
            "novel_translation_jobs.job_id",
            name="fk_chapter_translation_mappings_job_id_novel_translation_jobs",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    job_of_mapping: Mapped["NovelTranslationJob"] = relationship(back_populates="chapter_mappings_with_job")

    source_chapter_id = mapped_column(
        ForeignKey(
            "chapters.chapter_id",
            name="fk_chapter_translation_mappings_source_chapter_id_chapters",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    source_chapter_of_mapping: Mapped["Chapter"] = relationship(
        back_populates="source_mappings_with_chapter",
        foreign_keys=[source_chapter_id],
    )

    target_chapter_id = mapped_column(
        ForeignKey(
            "chapters.chapter_id",
            name="fk_chapter_translation_mappings_target_chapter_id_chapters",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    target_chapter_of_mapping: Mapped["Chapter | None"] = relationship(
        back_populates="target_mappings_with_chapter",
        foreign_keys=[target_chapter_id],
    )
