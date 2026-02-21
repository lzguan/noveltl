from typing import Any, Protocol

from sqlalchemy.orm import Session

from ..auth.models import User
from .schemas import (
    ApplyFilterOptionsBase,
    ContextBase,
    DecideInstancesOptionsBase,
    FlagInstancesOptionsBase,
    GetContextsOptionsBase,
    InstanceBase,
)


class Filter[FlagInstancesOptions : FlagInstancesOptionsBase,
             GetContextsOptions : GetContextsOptionsBase,
             DecideInstancesOptions : DecideInstancesOptionsBase,
             ApplyFilterOptions : ApplyFilterOptionsBase,
             Instance : InstanceBase,
             Context : ContextBase
            ](Protocol):
    """
    Abstract class for a filter used in autolabeling. See docs/requirements.md for more details.

    Attributes:
        description: Description of the filter.
        apply_filter: Callable that applies the filter to each instance in a list of instances.
    """

    description : str
    supports_decide : bool
    supports_apply : bool

    def get_instance_schema(self) -> dict[Any, Any]:
        """
        Returns the schema of the instance type used by the filter.
        """
        ...

    def get_context_schema(self) -> dict[Any, Any]:
        """
        Returns the schema of the context type used by the filter.
        """
        ...

    def get_flag_instances_options_schema(self) -> dict[Any, Any]:
        """
        Returns the schema of the options type used by the filter.
        """
        ...

    def get_get_contexts_options_schema(self) -> dict[Any, Any]:
        """
        Returns the schema of the options type used by the filter.
        """
        ...

    def get_decide_instances_options_schema(self) -> dict[Any, Any]:
        """
        Returns the schema of the options type used by the filter.
        """
        ...

    def get_apply_filter_options_schema(self) -> dict[Any, Any]:
        """
        Returns the schema of the options type used by the filter.
        """
        ...

    def flag_instances(self, db : Session, current_user : User, options : FlagInstancesOptions) -> list[Instance]:
        """
        Flags instances that meet certain criteria. May pull data from the database using a SQLAlchemy session.

        Args:
            db: SQLAlchemy session for database access.
            current_user: The user requesting the flagging.
            options: Options for flagging instances.

        Returns:
            List of flagged instances.
        """
        ...

    def get_contexts(self, db : Session, current_user : User, instances : list[Instance], options : GetContextsOptions) -> list[Context | None]:
        """
        Retrieves a list of contexts for a given list of instances from the database. Returns a list of contexts corresponding to the input instances. If an instance has no context, the corresponding entry is None.

        Args:
            db: SQLAlchemy session for database access.
            current_user: The user requesting the contexts.
            instances: List of instances to get contexts for.
            options: Options for getting contexts.
        """
        ...

    def decide_instances(self, db : Session, current_user : User, instance_contexts : list[tuple[Instance, Context]], options : DecideInstancesOptions) -> list[bool]:
        """
        Decides whether an instance passes the filter in a given context. Returns True if the instance passes the filter (i.e., should be included in `apply_filter`), False otherwise.

        Args:
            db: SQLAlchemy session for database access.
            current_user: The user requesting the decision.
            instance_contexts: List of tuples containing instances and their corresponding contexts.
            options: Options for deciding instances.
        """
        ...

    def apply_filter(self, db : Session, current_user : User, label_group_id : int, instances : list[Instance], options : ApplyFilterOptions) -> None:
        """
        Applies the filter to each instance in a list of instances.

        Args:
            db: SQLAlchemy session for database access.
            current_user: The user requesting the filter application.
            label_group_id: The ID of the label group to apply the filter to.
            instances: List of instances to apply the filter to.
            options: Options for applying the filter.
        """
        ...


