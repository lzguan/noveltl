"""
Top level schemas for the codebase. These are used across multiple modules, and should not import from any module other than standard library and pydantic to avoid circular imports.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationInfo, model_validator
from pydantic.alias_generators import to_camel


class Model(BaseModel):
    """
    Base Pydantic model for all models in this codebase to inherit from.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class SkipDefaultModel(Model):
    @model_validator(mode="before")
    @classmethod
    def validate_skip_defaults(cls, data: Any, info: ValidationInfo) -> Any:
        if info.context and info.context.get("skip_default_values"):
            if not isinstance(data, dict):
                raise ValueError("Data is not a dict.")
            fields_with_defaults = {k for k, v in cls.model_fields.items() if not v.is_required()}
            keys_set = {k for k, _ in data.items()}  # pyright: ignore[reportUnknownVariableType]
            missing = fields_with_defaults - keys_set
            if len(missing) > 0:
                raise ValueError(f"Fields not set: {missing}")

        return data  # pyright: ignore[reportUnknownVariableType]


class OperationStatus(Model):
    """
    Pydantic model to signal return status of operation.

    Attributes:
        status: One of "success", "fail".
        detail: Details on operation.

    Notes:
        Unless under exceptional circumstances, should not return fail and just raise an exception.
    """

    status: Literal["success", "fail"]
    detail: str | None = None


class DetailHTTPErrorResponse(Model):
    """
    Generic error payload for HTTPException responses that only return a detail string.

    Attributes:
        detail: Human-readable description of the error.
    """

    detail: str


class RequestConflictDetail(Model):
    """
    Structured detail payload used by request-key wrapped 409 responses.

    Attributes:
        detail: Human-readable description of the error.
        cache_conflict: Whether the failure was caused by a request-key cache conflict.
    """

    detail: str
    cache_conflict: bool


class RequestConflictErrorResponse(Model):
    """
    HTTPException response body for request-key wrapped 409 responses.

    Attributes:
        detail: Structured conflict detail.
    """

    detail: RequestConflictDetail
