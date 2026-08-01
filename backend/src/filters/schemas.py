from typing import Annotated, Self
from uuid import UUID

from pydantic import Field, TypeAdapter, model_validator

from src.filters.data_types import Schema
from src.filters.runners.python.group_runner import GroupData
from src.filters.runners.python.types import PythonRunnerInput
from src.schemas import Model

type RunnerInput = Annotated[PythonRunnerInput, Field(discriminator="runtime_name")]
runner_input_adapter = TypeAdapter(RunnerInput)


class GroupFilter(Model):
    grouping_id: UUID
    values: list[GroupData]


class FunctionDefinitionMeta(Model):
    function_definition_id: UUID
    namespace: str
    function_name: str


class Frame(Model):
    group_filters: list[GroupFilter]
    workflow_id: UUID
    sort_keys: list[tuple[str, bool]] = Field(default_factory=list)  # List of (field_name, ascending) tuples

    @model_validator(mode="after")
    def validate_group_filters(self) -> Self:
        ids = set()
        for group_filter in self.group_filters:
            if group_filter.grouping_id in ids:
                raise ValueError(f"Duplicate grouping_id {group_filter.grouping_id} in frame")
            ids.add(group_filter.grouping_id)
        return self

    @model_validator(mode="after")
    def validate_sort_keys(self) -> Self:
        if len(self.sort_keys) > 3:
            raise ValueError("At most 3 sort keys are allowed in a frame")
        if len(set(key for key, _ in self.sort_keys)) != len(self.sort_keys):
            raise ValueError("Duplicate sort keys are not allowed in a frame")
        return self


class InstanceQuery(Model):
    frame: Frame
    limit: int = Field(default=50, ge=1, le=100)
    cursor: UUID | None = Field(
        default=None,
        description="Cursor for pagination. If provided, must be a valid instance id. The query will return results after this cursor according to the sort keys.",
    )


def validate_frame_workflow(frame: Frame, schema: Schema):
    for sort_key, _ in frame.sort_keys:
        if sort_key not in schema.fields:
            raise ValueError(f"Sort key {sort_key} is not a valid field in the schema")
        if schema.fields[sort_key].type not in ("string", "int", "bool", "float"):
            raise ValueError(f"Sort key {sort_key} must be of type string, int, bool, or float")
