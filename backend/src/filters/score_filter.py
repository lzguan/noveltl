import uuid
from typing import Literal, Self

from pydantic import Field, model_validator
from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.orm import Session

from ..auth.models import User
from ..exceptions import UnknownError
from ..labels import models as label_models
from ..labels import schemas as label_schemas
from ..labels.permissions import label_data_mod_access_select, label_mod_access_delete
from ..novels import models as novel_models
from ..novels.exceptions import ChapterContentOutdatedException
from ..novels.permissions import chapter_content_mod_access_select
from .filter_base import (
    ApplyFilterOptionsBase,
    DecideInstancesOptionsBase,
    Filter,
    FlagInstancesOptionsBase,
    GetContextsOptionsBase,
)
from .schemas import SentenceContext, SingleLabel
from .utils import copy_label_group, find_sentence_around


class DecideLengthError(ValueError):
    pass

class ScoreFlagInstancesOptions(FlagInstancesOptionsBase):
    type : Literal["score_filter_flag_instance_options"] = "score_filter_flag_instance_options"
    label_group_id : uuid.UUID = Field(..., description="ID of the label group to consider.")
    start : int | None = Field(default=None, ge=0, description="Minimum chapter number (inclusive) to consider.")
    end : int | None = Field(default=None, ge=0, description="Maximum chapter number (exclusive) to consider.")
    flag_dirty : bool = Field(
        default=False,
        description="Whether to include dirty labels when flagging instances."
    )
    min_score : float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode='after')
    def check_start_end(self) -> Self:
        if self.start is not None and self.end is not None:
            if self.start >= self.end:
                raise ValueError("start must be less than end")
        return self

class ScoreGetContextOptions(GetContextsOptionsBase):
    type : Literal["score_filter_get_context_options"] = "score_filter_get_context_options"
    delimiters : str = Field(
        default=".!?。！？\n",
        description="String of delimiter characters used to identify sentence boundaries."
    )
    refresh : bool = Field(
        default=False,
        description="Whether to refresh the context even if it was previously computed. If set to True, the SentenceContext.label field will be set to the label associated with the instance within the database, or None if it doesn't exist. If set to False, the SentenceContext.label field will always be None."
    )

class ScoreDecideInstancesOptions(DecideInstancesOptionsBase):
    type : Literal["score_filter_decide_instances_options"] = "score_filter_decide_instances_options"
    mode : Literal["auto", "manual"] = Field(
        default="auto",
        description="Whether to automatically decide if an instance passes the filter or to let the user decide manually."
    )
    exclude_phrases : list[str] = Field(
        default_factory=list,
        description="List of phrases to exclude. Only applies for auto mode. If any of the phrases in this list are found in the context text, the instance will automatically fail the filter."
    )
    decisions : list[bool] = Field(
        default_factory=lambda: [],
        description="List of decisions for each instance, where True means the instance passes the filter and False means it fails. Only used in manual mode. Must be the same length as the number of instances passed to decide_instances."
    )

class ScoreApplyFilterOptions(ApplyFilterOptionsBase):
    type : Literal["score_filter_apply_filter_options"] = "score_filter_apply_filter_options"
    label_group_id : uuid.UUID = Field(..., description="ID of the label group to apply the filter to.")


class ScoreFilter(Filter[ScoreFlagInstancesOptions, ScoreGetContextOptions, ScoreDecideInstancesOptions, ScoreApplyFilterOptions, SingleLabel, SentenceContext]):
    def __init__(self):
        self.description = "Flags label instances based on score thresholds and text content."
        self.supports_decide = True
        self.supports_apply = True

    context_schema = SentenceContext
    instance_schema = SingleLabel
    flag_instances_options_schema = ScoreFlagInstancesOptions
    get_contexts_options_schema = ScoreGetContextOptions
    decide_instances_options_schema = ScoreDecideInstancesOptions
    apply_filter_options_schema = ScoreApplyFilterOptions

    def flag_instances(self, db : Session, current_user : User, options : ScoreFlagInstancesOptions) -> list[SingleLabel]:
        q = select(
            label_models.Label, novel_models.ChapterContent.chapter_content_id
        ).where(
            label_models.Label.label_score < options.min_score
        ).join(
            label_models.LabelData,
            label_models.Label.label_data_id == label_models.LabelData.label_data_id
        ).join(
            novel_models.ChapterContent,
            label_models.LabelData.chapter_content_id == novel_models.ChapterContent.chapter_content_id
        ).join(
            novel_models.Chapter,
            novel_models.ChapterContent.chapter_id == novel_models.Chapter.chapter_id
        ).where(
            label_models.LabelData.label_group_id == options.label_group_id
        ).where(
            novel_models.ChapterContent.chapter_content_version == select(
                func.max(novel_models.ChapterContent.chapter_content_version)
            ).where(
                novel_models.ChapterContent.chapter_id == novel_models.Chapter.chapter_id
            ).correlate(novel_models.Chapter).scalar_subquery()
        )
        if not options.flag_dirty:
            q = q.where(label_models.Label.label_dirty.is_(False))
        if options.start is not None:
            q = q.where(novel_models.Chapter.chapter_num >= options.start)
        if options.end is not None:
            q = q.where(novel_models.Chapter.chapter_num < options.end)
        q = label_data_mod_access_select(q, current_user)

        result = db.execute(q)
        result_rows = result.all()

        return [SingleLabel(label=label_schemas.Label.model_validate(label), chapter_content_id=id) for label, id in result_rows]

    def get_contexts(self, db : Session, current_user : User, instances : list[SingleLabel], options : ScoreGetContextOptions) -> list[SentenceContext | None]:
        chapter_content_ids = list({instance.chapter_content_id for instance in instances})
        q = select(
            novel_models.ChapterContent
        ).where(
            novel_models.ChapterContent.chapter_content_id.in_(chapter_content_ids)
        ).join(
            novel_models.Chapter,
            novel_models.ChapterContent.chapter_id == novel_models.Chapter.chapter_id
        ).where(
            novel_models.ChapterContent.chapter_content_version == select(
                func.max(novel_models.ChapterContent.chapter_content_version)
            ).where(
                novel_models.ChapterContent.chapter_id == novel_models.Chapter.chapter_id
            ).correlate(novel_models.Chapter).scalar_subquery()
        )
        q = chapter_content_mod_access_select(q, current_user)
        result = db.execute(q)
        result_rows = result.scalars().all()
        chapter_content_map = {chapter_content.chapter_content_id: chapter_content for chapter_content in result_rows}

        output : list[SentenceContext | None] = []
        for instance in instances:
            if instance.chapter_content_id not in chapter_content_map:
                output.append(None)
                continue
            chapter_content = chapter_content_map[instance.chapter_content_id]
            sentence, label_start_rel, label_end_rel = find_sentence_around(
                chapter_content.chapter_content_text,
                instance.label.label_start,
                instance.label.label_end,
                options.delimiters
            )
            output.append(SentenceContext(
                text=sentence,
                label_start_rel=label_start_rel,
                label_end_rel=label_end_rel,
                chapter_content_id=instance.chapter_content_id,
            ))
        return output


    def _check_instances_not_stale(self, db : Session, current_user : User, chapter_content_ids : set[uuid.UUID]) -> None:
        """Check that all chapter_content_ids are still the latest version. Raises ChapterContentOutdatedException if any are stale."""
        if not chapter_content_ids:
            return
        q = select(
            novel_models.ChapterContent.chapter_content_id
        ).join(
            novel_models.Chapter,
            novel_models.ChapterContent.chapter_id == novel_models.Chapter.chapter_id
        ).where(
            novel_models.ChapterContent.chapter_content_id.in_(chapter_content_ids)
        ).where(
            novel_models.ChapterContent.chapter_content_version == select(
                func.max(novel_models.ChapterContent.chapter_content_version)
            ).where(
                novel_models.ChapterContent.chapter_id == novel_models.Chapter.chapter_id
            ).correlate(novel_models.Chapter).scalar_subquery()
        )
        q = chapter_content_mod_access_select(q, current_user)
        current_ids = set(db.execute(q).scalars().all())
        stale_ids = chapter_content_ids - current_ids
        if stale_ids:
            raise ChapterContentOutdatedException(
                f"Instances reference stale chapter content version(s): {stale_ids}. Please refresh and try again."
            )

    def decide_instances(self, db : Session, current_user : User, instance_contexts : list[tuple[SingleLabel, SentenceContext | None]], options : ScoreDecideInstancesOptions) -> list[bool]:
        """
        See the base class for method signature and docstring. The implementation should use the context text and the exclude_phrases option to automatically decide if an instance passes the filter when in auto mode, or use the decisions provided in options when in manual mode.

        Raises:
            DecideLengthError: If in manual mode and the length of options.decisions does not match the length of instance_contexts.
            ChapterContentOutdatedException: If any instances reference a stale chapter content version.
        """
        self._check_instances_not_stale(db, current_user, {inst.chapter_content_id for inst, _ in instance_contexts})
        if options.mode == "auto":
            decisions : list[bool] = []
            for instance, _ in instance_contexts:
                if any(phrase in instance.label.label_word for phrase in options.exclude_phrases):
                    decisions.append(False)
                else:
                    decisions.append(True)
            return decisions
        else:
            if len(options.decisions) != len(instance_contexts):
                raise DecideLengthError("Length of decisions must match length of instance_contexts in manual mode")
            return options.decisions

    def apply_filter(self, db : Session, current_user : User, instances : list[SingleLabel], options : ScoreApplyFilterOptions) -> None:
        label_group_id = options.label_group_id
        if options.create_copy:
            new_label_group = copy_label_group(db, current_user, label_group_id, str(options.new_label_group_name))
            label_group_id = new_label_group.label_group_id

        instance_tuples = [
            (
                instance.chapter_content_id,
                instance.label.label_start,
                instance.label.label_end,
                instance.label.label_word,
            ) for instance in instances
        ]

        sub_q = select(
            label_models.LabelData
        ).where(
            label_models.LabelData.label_group_id == label_group_id
        ).subquery()

        stmt = delete(label_models.Label).where(
            label_models.Label.label_data_id.in_(
                select(sub_q.c.label_data_id)
            )
        ).where(
            tuple_(
                select(sub_q.c.chapter_content_id).where(
                    sub_q.c.label_data_id == label_models.Label.label_data_id
                ).correlate(label_models.Label).scalar_subquery(),
                label_models.Label.label_start,
                label_models.Label.label_end,
                label_models.Label.label_word,
            ).in_(instance_tuples)
        )
        stmt = label_mod_access_delete(stmt, current_user)
        try:
            self._check_instances_not_stale(db, current_user, {inst.chapter_content_id for inst in instances})
            db.execute(stmt)
            db.commit()
        except ChapterContentOutdatedException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise UnknownError("An error occurred while applying the filter. Please try again later.") from e
