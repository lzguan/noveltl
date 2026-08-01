from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID

from pydantic import ConfigDict, Field, TypeAdapter, model_validator

from src.filters.data_types import DataObj, FieldName, Schema
from src.filters.exceptions import InvalidSortKeyException, UnsupportedSortTypeException
from src.filters.runners.python.group_runner import GroupData
from src.filters.runners.python.types import PythonRunnerInput
from src.schemas import Model

type RunnerInput = Annotated[PythonRunnerInput, Field(discriminator="runtime_name")]
runner_input_adapter = TypeAdapter(RunnerInput)


class GroupFilter(Model):
    grouping_id: UUID
    values: list[GroupData] = Field(max_length=100)


class FunctionDefinitionMeta(Model):
    function_definition_id: UUID
    namespace: str
    function_name: str


class InstanceResponse(Model):
    model_config = ConfigDict(from_attributes=True)

    instance_id: UUID
    workflow_id: UUID
    value: DataObj


class InstanceQueryResult(Model):
    instance: InstanceResponse
    group_values: dict[UUID, GroupData]


class SortDirection(StrEnum):
    ASCENDING = "asc"
    DESCENDING = "desc"


class SortKey(Model):
    field_name: FieldName
    direction: SortDirection


class Frame(Model):
    group_filters: list[GroupFilter] = Field(max_length=10)
    workflow_id: UUID
    sort_keys: list[SortKey] = Field(default_factory=list, max_length=3)

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
        if len({sort_key.field_name for sort_key in self.sort_keys}) != len(self.sort_keys):
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
    for sort_key in frame.sort_keys:
        if sort_key.field_name not in schema.fields:
            raise InvalidSortKeyException(f"Sort key {sort_key.field_name} is not a valid field in the schema")
        if schema.fields[sort_key.field_name].type not in ("string", "int", "bool", "float"):
            raise UnsupportedSortTypeException(
                f"Sort key {sort_key.field_name} must be of type string, int, bool, or float"
            )
