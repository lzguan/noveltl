from collections.abc import Sequence
from typing import Annotated, Any, Protocol, TypedDict

from pydantic import Field
from sqlalchemy.orm import Session

from ..auth.models import User
from .schemas import (
    ApplyFilterOptionsBase,
    ContextBase,
    DecideInstancesOptionsBase,
    FlagInstancesOptionsBase,
    GetContextsOptionsBase,
    InstanceBase,
    ParagraphContext,
    SentenceContext,
    SingleLabel,
)
from .score_filter import (
    ScoreApplyFilterOptions,
    ScoreDecideInstancesOptions,
    ScoreFlagInstancesOptions,
    ScoreGetContextOptions,
)

Instance = Annotated[SingleLabel, Field(discriminator="type")]
Context = Annotated[SentenceContext | ParagraphContext, Field(discriminator="type")]
FlagInstancesOptions = Annotated[ScoreFlagInstancesOptions, Field(discriminator="type")]
GetContextsOptions = Annotated[ScoreGetContextOptions, Field(discriminator="type")]
DecideInstancesOptions = Annotated[ScoreDecideInstancesOptions, Field(discriminator="type")]
ApplyFilterOptions = Annotated[ScoreApplyFilterOptions, Field(discriminator="type")]

class RegisteredFilter(Protocol):
    """
    A non-generic protocol used strictly for the dynamic registry.
    This restores type hinting for Pydantic schema generation.
    """
    description: str
    supports_decide: bool
    supports_apply: bool

    @property
    def instance_schema(self) -> type[InstanceBase]: ...

    @property
    def context_schema(self) -> type[ContextBase]: ...

    @property
    def flag_instances_options_schema(self) -> type[FlagInstancesOptionsBase]: ...

    @property
    def get_contexts_options_schema(self) -> type[GetContextsOptionsBase]: ...

    @property
    def decide_instances_options_schema(self) -> type[DecideInstancesOptionsBase]: ...

    @property
    def apply_filter_options_schema(self) -> type[ApplyFilterOptionsBase]: ...

    # 2. Execution (Erased for the registry)
    def flag_instances(self, db: Session, current_user: User, options: Any) -> Sequence[Instance]: ...
    def get_contexts(self, db: Session, current_user: User, instances: list[Any], options: Any) -> Sequence[Context | None]: ...
    def decide_instances(self, db: Session, current_user: User, instance_contexts: list[tuple[Any, Any]], options: Any) -> Sequence[bool]: ...
    def apply_filter(self, db: Session, current_user: User, label_group_id: int, instances: list[Any], options: Any) -> None: ...

class SchemaInfo(TypedDict):
    description : str
    supports_decide : bool
    supports_apply : bool
    instance_schema : dict[Any, Any]
    context_schema : dict[Any, Any]
    flag_instances_options_schema : dict[Any, Any]
    get_contexts_options_schema : dict[Any, Any]
    decide_instances_options_schema : dict[Any, Any]
    apply_filter_options_schema : dict[Any, Any]
