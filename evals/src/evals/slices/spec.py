from dataclasses import dataclass
from typing import Annotated, Literal
from uuid import UUID

from pydantic import MISSING, BaseModel, ConfigDict, Field, model_validator

type ChapterNum = Annotated[int, Field(ge=0, strict=True)]
type Horizon = ChapterNum | None
type KindHorizon = ChapterNum | None | Literal[False]


class SpecModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NovelSlice(SpecModel):
    novel_id: UUID
    horizon: Horizon | MISSING = Field(
        default=MISSING,
        description=(
            "Chapters numbered above this are deleted; unset inherits the slice horizon and None keeps every chapter. "
            "Assumes the novel numbers its chapters one-to-one with the source novel it translates."
        ),
    )


class GroupSlice(SpecModel):
    group_id: UUID
    horizon: Horizon | MISSING = MISSING
    terms: KindHorizon | MISSING = MISSING
    term_translations: KindHorizon | MISSING = MISSING
    memories: KindHorizon | MISSING = MISSING
    conventions: KindHorizon | MISSING = MISSING


@dataclass(frozen=True)
class GroupCut:
    terms: KindHorizon
    term_translations: KindHorizon
    memories: KindHorizon
    conventions: KindHorizon


def _rank(horizon: KindHorizon) -> float:
    if horizon is None:
        return float("inf")
    if horizon is False:
        return float("-inf")
    return horizon


def _inherit[T](value: T | MISSING, default: T) -> T:
    return default if value is MISSING else value


class Slice(SpecModel):
    horizon: Horizon = None
    novels: list[NovelSlice] = []
    groups: list[GroupSlice] = []

    def novel_cuts(self) -> dict[UUID, Horizon]:
        return {novel.novel_id: _inherit(novel.horizon, self.horizon) for novel in self.novels}

    def group_cuts(self) -> dict[UUID, GroupCut]:
        cuts: dict[UUID, GroupCut] = {}
        for group in self.groups:
            horizon = _inherit(group.horizon, self.horizon)
            cuts[group.group_id] = GroupCut(
                terms=_inherit(group.terms, horizon),
                term_translations=_inherit(group.term_translations, horizon),
                memories=_inherit(group.memories, horizon),
                conventions=_inherit(group.conventions, horizon),
            )
        return cuts

    @model_validator(mode="after")
    def check_static_consistency(self) -> Slice:
        for label, ids in (
            ("novel", [novel.novel_id for novel in self.novels]),
            ("group", [group.group_id for group in self.groups]),
        ):
            duplicates = sorted({str(item) for item in ids if ids.count(item) > 1})
            if duplicates:
                raise ValueError(f"Each {label} may appear once; repeated: {', '.join(duplicates)}")
        for group_id, cut in self.group_cuts().items():
            if _rank(cut.term_translations) > _rank(cut.terms):
                raise ValueError(f"Group {group_id}: term_translations must not extend past terms")
            if _rank(cut.memories) > _rank(cut.terms):
                raise ValueError(f"Group {group_id}: memories must not extend past terms")
        return self
