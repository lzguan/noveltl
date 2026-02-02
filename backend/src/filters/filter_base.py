from typing import Any, Protocol

from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth.models import User


class OptionsBase(BaseModel):
    pass

class InstanceBase(BaseModel):
    pass

class ContextBase(BaseModel):
    pass

class Filter[FlagInstanceOptions : OptionsBase,
             GetContextOptions : OptionsBase,
             DecideInstanceOptions : OptionsBase,
             ApplyFilterOptions : OptionsBase,
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

    def get_get_context_options_schema(self) -> dict[Any, Any]:
        """
        Returns the schema of the options type used by the filter.
        """
        ...

    def get_decide_instance_options_schema(self) -> dict[Any, Any]:
        """
        Returns the schema of the options type used by the filter.
        """
        ...

    def flag_instances(self, db : Session, current_user : User, options : FlagInstanceOptions) -> list[Instance]:
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

    def get_contexts(self, db : Session, current_user : User, instances : list[Instance], options : GetContextOptions) -> list[Context | None]:
        """
        Retrieves a list of contexts for a given list of instances from the database. Returns a list of contexts corresponding to the input instances. If an instance has no context, the corresponding entry is None.

        Args:
            db: SQLAlchemy session for database access.
            current_user: The user requesting the contexts.
            instances: List of instances to get contexts for.
            options: Options for getting contexts.
        """
        ...

    def decide_instance(self, db : Session, current_user : User, instance_contexts : list[tuple[Instance, Context]], options : DecideInstanceOptions) -> bool:
        """
        Decides whether an instance passes the filter in a given context.

        Args:
            db: SQLAlchemy session for database access.
            current_user: The user requesting the decision.
            instance_contexts: List of tuples containing instances and their corresponding contexts.
            options: Options for deciding instances.
        """
        ...

    def apply_filter(self, db : Session, current_user : User, instances : list[Instance], options : ApplyFilterOptions) -> list[Instance]:
        """
        Applies the filter to each instance in a list of instances.

        Args:
            db: SQLAlchemy session for database access.
            instances: List of instances to apply the filter to.
            options: Options for deciding instances.
        """
        ...


