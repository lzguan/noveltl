from typing import Any, Literal, Self

from pydantic import Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.models import User
from ..labels import models as label_models
from ..labels import schemas as label_schemas
from ..labels.permissions import label_data_mod_access_select
from ..novels import models as novel_models
from ..novels.permissions import raw_chapter_revision_mod_access_select
from .filter_base import ContextBase, Filter, InstanceBase, OptionsBase
from .utils import find_sentence_around


class SentenceContext(ContextBase):
    type : Literal["sentence"] = "sentence"
    text: str
    label_start: int
    label_end: int
    raw_chapter_revision_id : int

class SingleLabel(InstanceBase):
    type : Literal["single_label"] = "single_label"
    label : label_schemas.Label
    raw_chapter_revision_id : int

class ScoreFlagInstancesOptions(OptionsBase):
    type : Literal["score_filter_flag_instance_options"] = "score_filter_flag_instance_options"
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

class ScoreGetContextOptions(OptionsBase):
    type : Literal["score_filter_get_context_options"] = "score_filter_get_context_options"
    delimiters : str = Field(
        default=".!?。！？\n",
        description="String of delimiter characters used to identify sentence boundaries."
    )

class ScoreDecideInstanceOptions(OptionsBase):
    type : Literal["score_filter_decide_instance_options"] = "score_filter_decide_instance_options"
    target_phrases : list[str] = Field(
        default_factory=list,
        description="List of phrases to look for in the sentence context. If empty, all sentences pass."
    )

class ScoreApplyFilterOptions(OptionsBase):
    type : Literal["score_filter_apply_filter_options"] = "score_filter_apply_filter_options"


class ScoreFilter(Filter[ScoreFlagInstancesOptions, ScoreGetContextOptions, ScoreDecideInstanceOptions, ScoreApplyFilterOptions, SingleLabel, SentenceContext]):
    description : str = "Flags label instances based on score thresholds and text content."

    def get_instance_schema(self) -> dict[Any, Any]:
        return SingleLabel.model_json_schema()

    def get_context_schema(self) -> dict[Any, Any]:
        return SentenceContext.model_json_schema()

    def get_flag_instances_options_schema(self) -> dict[Any, Any]:
        return ScoreFlagInstancesOptions.model_json_schema()

    def get_get_context_options_schema(self) -> dict[Any, Any]:
        return ScoreGetContextOptions.model_json_schema()

    def get_decide_instance_options_schema(self) -> dict[Any, Any]:
        return ScoreDecideInstanceOptions.model_json_schema()

    def flag_instances(self, db : Session, current_user : User, options : ScoreFlagInstancesOptions) -> list[SingleLabel]:
        q = select(
            label_models.Label, novel_models.RawChapterRevision.raw_chapter_revision_id
        ).where(
            label_models.Label.label_score >= options.min_score
        ).join(
            label_models.LabelData,
            label_models.Label.label_data_id == label_models.LabelData.label_data_id
        ).join(
            novel_models.RawChapterRevision,
            label_models.LabelData.raw_chapter_revision_id == novel_models.RawChapterRevision.raw_chapter_revision_id
        ).join(
            novel_models.RawChapter,
            novel_models.RawChapterRevision.raw_chapter_id == novel_models.RawChapter.raw_chapter_id
        )
        q = label_data_mod_access_select(q, current_user)
        q = raw_chapter_revision_mod_access_select(q, current_user)
        if not options.flag_dirty:
            q = q.where(label_models.Label.label_dirty.is_(False))
        if options.start is not None:
            q = q.where(novel_models.RawChapter.raw_chapter_num >= options.start)
        if options.end is not None:
            q = q.where(novel_models.RawChapter.raw_chapter_num < options.end)

        result = db.execute(q)
        result_rows = result.all()

        return [SingleLabel(label=label_schemas.Label.model_validate(label), raw_chapter_revision_id=id) for label, id in result_rows]

    def get_contexts(self, db : Session, current_user : User, instances : list[SingleLabel], options : ScoreGetContextOptions) -> list[SentenceContext | None]:
        revision_ids = list({instance.raw_chapter_revision_id for instance in instances})
        q = select(
            novel_models.RawChapterRevision
        ).where(
            novel_models.RawChapterRevision.raw_chapter_revision_id.in_(revision_ids)
        )
        q = raw_chapter_revision_mod_access_select(q, current_user)
        result = db.execute(q)
        result_rows = result.scalars().all()
        revision_map = {rev.raw_chapter_revision_id: rev for rev in result_rows}

        output : list[SentenceContext | None] = []
        for instance in instances:
            if instance.raw_chapter_revision_id not in revision_map:
                output.append(None)
                continue
            revision = revision_map[instance.raw_chapter_revision_id]
            sentence, label_start, label_end = find_sentence_around(
                revision.raw_chapter_revision_text,
                instance.label.label_start,
                instance.label.label_end,
                options.delimiters
            )
            output.append(SentenceContext(
                text=sentence,
                label_start=label_start,
                label_end=label_end,
                raw_chapter_revision_id=instance.raw_chapter_revision_id
            ))
        return output


    def decide_instance(self, db : Session, current_user : User, instance_contexts : list[tuple[SingleLabel, SentenceContext]], options : ScoreDecideInstanceOptions) -> bool:
        # Implementation to decide if a label instance passes the filter based on its context
        ...

    def apply_filter(self, db : Session, current_user : User, instances : list[SingleLabel], options : ScoreApplyFilterOptions) -> list[SingleLabel]:
        # Implementation to apply the filter to a list of label instances
        ...
