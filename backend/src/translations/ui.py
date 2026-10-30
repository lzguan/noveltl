"""Presentation annotations embedded in action configuration JSON Schema."""

from typing import Literal, Self

from pydantic import ConfigDict, model_validator

from src.schemas import Model


class UIHints(Model):
    model_config = ConfigDict(extra="forbid")

    control: (
        Literal["number", "text", "textarea", "select", "checkbox", "filter-checklist", "resource-picker"] | None
    ) = None
    resource: Literal["memory-group"] | None = None
    scope: Literal["current-novel"] | None = None
    placement: Literal["job-inputs"] | None = None
    stage_scope: Literal["first"] | None = None
    show_after: str | None = None
    placeholder: str | None = None
    null_label: str | None = None
    empty_label: str | None = None

    @model_validator(mode="after")
    def validate_resource(self) -> Self:
        if self.control == "resource-picker":
            if self.resource is None or self.scope is None:
                raise ValueError("Resource pickers require resource and scope")
        elif self.resource is not None or self.scope is not None or self.placement is not None:
            raise ValueError("Resource, scope and placement require a resource picker")
        return self

    def schema_extra(self) -> dict:
        return {"x-ui": self.model_dump(mode="json", by_alias=True, exclude_none=True)}
