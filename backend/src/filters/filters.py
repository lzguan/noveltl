from typing import Protocol

from pydantic import BaseModel
from sqlalchemy.orm import Session


class OptionsBase(BaseModel):
    pass

class InstanceBase(BaseModel):
    """
    This is a base class for instances used in autolabel filters. Should implement the type attribute, which is a string representing the type of instance (e.g., "chapter_revision", "novel", etc.).
    """
    pass

class ContextBase(BaseModel):
    pass

class ContextGetter[Instance : InstanceBase, Context : ContextBase](Protocol):
    def __call__(self, db : Session, instance : Instance) -> list[Context]:
        """
        Callable that retrieves a list of contexts for a given instance from the database.

        Args:
            db: SQLAlchemy session for database access.
            instance: The instance for which to retrieve contexts.
        """
        ...

class InstanceDecider[Instance : InstanceBase, Context : ContextBase](Protocol):
    def __call__(self, db : Session, instance : Instance, context : Context, *args) -> bool:
        """
        Callable that decides whether an instance passes the filter in a given context.

        Args:
            instance: The instance to evaluate.
            context: The context in which to evaluate the instance.
        """
        ...

class Filter[Options : OptionsBase, Instance : InstanceBase, Context : ContextBase](Protocol):
    """
    Abstract class for a filter used in autolabeling. See docs/requirements.md for more details.

    Attributes:
        description: Description of the filter.
        instance_type: Type of instance the filter applies to.
        context_type: Type of context the filter uses.
        flag_instances: Callable that returns a list of instances to be flagged.
        get_context_list: List of callables that return contexts for filtering.
        decide_instance: Callable that decides whether an instance passes the filter in a given context.
        apply_filter: Callable that applies the filter to each instance in a list of instances.
    """

    description : str
    instance_type : str
    context_type : str

    def flag_instances(self, db : Session, options : Options) -> list[Instance]:
        """
        Flags instances that meet certain criteria. Pulls data from the database using a SQLAlchemy session.

        Returns:
            List of flagged instances.
        """
        ...

    """
    A mapping from context getter names context getter callables.
    """
    get_context_list : dict[str, ContextGetter[Instance, Context]]

    """
    A mapping from instance decider names to instance decider callables.
    """
    decide_instance_list : dict[str, InstanceDecider[Instance, Context]]

    def apply_filter(self, db : Session, instances : list[Instance]) -> list[Instance]:
        """
        Applies the filter to each instance in a list of instances.

        Args:
            db: SQLAlchemy session for database access.
            instances: List of instances to apply the filter to.
        """
        ...


