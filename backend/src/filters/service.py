from typing import Any

from sqlalchemy.orm import Session

from ..auth.models import User
from .exceptions import (
    FilterNotFoundException,
    InstanceContextValidationException,
    InstanceValidationException,
    OptionsValidationException,
)
from .score_filter import ScoreFilter
from .types import (
    Context,
    Instance,
    RegisteredFilter,
    SchemaInfo,
)

# use kebab-case for filter names in the registry to match URL path parameters
FILTER_REGISTRY: dict[str, RegisteredFilter] = {
    "score-filter": ScoreFilter(),
}


def query_schemas() -> dict[str, SchemaInfo]:
    """
    Queries the FILTER_REGISTRY to retrieve the schemas for all registered filters.
    """
    return {
        filter_name: SchemaInfo(
            description=filter.description,
            supports_decide=filter.supports_decide,
            supports_apply=filter.supports_apply,
            instance_schema=filter.instance_schema.model_json_schema(),
            context_schema=filter.context_schema.model_json_schema(),
            flag_instances_options_schema=filter.flag_instances_options_schema.model_json_schema(),
            get_contexts_options_schema=filter.get_contexts_options_schema.model_json_schema(),
            decide_instances_options_schema=filter.decide_instances_options_schema.model_json_schema(),
            apply_filter_options_schema=filter.apply_filter_options_schema.model_json_schema(),
        )
        for filter_name, filter in FILTER_REGISTRY.items()
    }


def flag_instances(db: Session, current_user: User, filter_name: str, options: Any) -> list[Instance]:
    """
    Flags instances using a specified filter and options.

    Args:
        db: Database session for any necessary database access during filtering.
        current_user: The user making the request, which may be relevant for certain filters.
        filter_name: The name of the filter to use.
        options: The options for flagging instances, which will be validated against the filter's schema
    """
    if filter_name not in FILTER_REGISTRY:
        raise FilterNotFoundException(f"Filter {filter_name} not found in registry")
    filter = FILTER_REGISTRY[filter_name]
    try:
        validated_options = filter.flag_instances_options_schema.model_validate(options)
    except ValueError as e:
        raise OptionsValidationException(f"Invalid options for filter {filter_name}: {e}") from e
    return list(filter.flag_instances(db, current_user, validated_options))


def get_contexts(
    db: Session, current_user: User, filter_name: str, instances: list[Any], options: Any
) -> list[Context | None]:
    if filter_name not in FILTER_REGISTRY:
        raise FilterNotFoundException(f"Filter {filter_name} not found in registry")
    filter = FILTER_REGISTRY[filter_name]
    try:
        validated_options = filter.get_contexts_options_schema.model_validate(options)
    except ValueError as e:
        raise OptionsValidationException(f"Invalid options for filter {filter_name}: {e}") from e
    try:
        validated_instances = [filter.instance_schema.model_validate(instance) for instance in instances]
    except ValueError as e:
        raise InstanceValidationException(f"Invalid instances for filter {filter_name}: {e}") from e
    return list(filter.get_contexts(db, current_user, validated_instances, validated_options))


def decide_instances(
    db: Session, current_user: User, filter_name: str, instance_contexts: list[Any], options: Any
) -> list[bool]:
    if filter_name not in FILTER_REGISTRY:
        raise FilterNotFoundException(f"Filter {filter_name} not found in registry")
    filter = FILTER_REGISTRY[filter_name]
    try:
        validated_options = filter.decide_instances_options_schema.model_validate(options)
    except ValueError as e:
        raise OptionsValidationException(f"Invalid options for filter {filter_name}: {e}") from e
    try:
        validated_instance_contexts = [
            (
                filter.instance_schema.model_validate(instance),
                filter.context_schema.model_validate(context) if context is not None else None,
            )
            for instance, context in instance_contexts
        ]
    except ValueError as e:
        raise InstanceContextValidationException(f"Invalid instances or contexts for filter {filter_name}: {e}") from e
    return list(filter.decide_instances(db, current_user, validated_instance_contexts, validated_options))


def apply_filter(db: Session, current_user: User, filter_name: str, instances: list[Any], options: Any) -> None:
    if filter_name not in FILTER_REGISTRY:
        raise FilterNotFoundException(f"Filter {filter_name} not found in registry")
    filter = FILTER_REGISTRY[filter_name]
    try:
        validated_options = filter.apply_filter_options_schema.model_validate(options)
    except ValueError as e:
        raise OptionsValidationException(f"Invalid options for filter {filter_name}: {e}") from e
    try:
        validated_instances = [filter.instance_schema.model_validate(instance) for instance in instances]
    except ValueError as e:
        raise InstanceValidationException(f"Invalid instances for filter {filter_name}: {e}") from e
    return filter.apply_filter(db, current_user, validated_instances, validated_options)
