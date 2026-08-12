import uuid
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, StringConstraints, TypeAdapter, model_validator

from src.schemas import Model

# Parse-time limits keep user-authored schemas and function descriptions from
# allocating unbounded Python objects. Limits on recursive AST depth and total
# workflow operations belong in the later semantic-validation pass.
MAX_FIELD_NAME_LENGTH = 128
MAX_SCHEMA_FIELDS = 256

# Schema types

type ElementaryTypeName = Literal["string", "int", "float", "bool", "labelRef", "textSpan"]
type FieldName = Annotated[
    str,
    StringConstraints(
        strict=True,
        min_length=1,
        max_length=MAX_FIELD_NAME_LENGTH,
        pattern=r".*\S.*",
    ),
]

# Elementary JSON values use strict parsing. In particular, booleans and
# numeric strings must not silently become integers, and non-finite floats are
# rejected because they do not have portable JSON, SQL, or comparison semantics.
type StringValue = Annotated[str, Field(strict=True)]
type IntegerValue = Annotated[int, Field(strict=True)]
type FloatValue = Annotated[float, Field(strict=True, allow_inf_nan=False)]
type BooleanValue = Annotated[bool, Field(strict=True)]


class SchemaFieldBase(Model):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["field"] = "field"
    type: ElementaryTypeName
    mutable: bool


class StringField(SchemaFieldBase):
    type: Literal["string"] = "string"
    mutable: bool = False


class IntField(SchemaFieldBase):
    type: Literal["int"] = "int"
    mutable: bool = False


class FloatField(SchemaFieldBase):
    type: Literal["float"] = "float"
    mutable: bool = False


class BoolField(SchemaFieldBase):
    type: Literal["bool"] = "bool"
    mutable: bool = False


class LabelRefField(SchemaFieldBase):
    type: Literal["labelRef"] = "labelRef"
    mutable: Literal[False] = False


class TextSpanField(SchemaFieldBase):
    type: Literal["textSpan"] = "textSpan"
    mutable: Literal[False] = False


type SchemaField = Annotated[
    StringField | IntField | FloatField | BoolField | LabelRefField | TextSpanField,
    Field(discriminator="type"),
]


class Schema(Model):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["schema"] = "schema"
    fields: dict[FieldName, SchemaField] = Field(default_factory=dict, max_length=MAX_SCHEMA_FIELDS)


type SObj = Annotated[Schema | SchemaField, Field(discriminator="kind")]

schema_adapter = TypeAdapter[SObj](SObj)

# Data types


class ChapterRef(Model):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chapter_id: uuid.UUID
    chapter_content_id: uuid.UUID


class TextSpan(ChapterRef):
    start: IntegerValue = Field(ge=0)
    end: IntegerValue = Field(ge=0)

    @model_validator(mode="after")
    def validate_range(self) -> "TextSpan":
        if self.end < self.start:
            raise ValueError("Text span end must be greater than or equal to its start.")
        return self


class LabelRef(ChapterRef):
    label_id: uuid.UUID
    label_data_id: uuid.UUID
    label_group_id: uuid.UUID


class DTypeBase[T](Model):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: T
    type: str
    kind: Literal["value"] = "value"


class StringData(DTypeBase[StringValue]):
    type: Literal["string"] = "string"


class IntData(DTypeBase[IntegerValue]):
    type: Literal["int"] = "int"


class FloatData(DTypeBase[FloatValue]):
    type: Literal["float"] = "float"


class BoolData(DTypeBase[BooleanValue]):
    type: Literal["bool"] = "bool"


class TextSpanData(DTypeBase[TextSpan]):
    type: Literal["textSpan"] = "textSpan"


class LabelRefData(DTypeBase[LabelRef]):
    type: Literal["labelRef"] = "labelRef"


type MDataType = Annotated[
    StringData | IntData | FloatData | BoolData,
    Field(discriminator="type"),
]
m_data_type_adapter = TypeAdapter[MDataType](MDataType)

type DataType = Annotated[
    StringData | IntData | FloatData | BoolData | TextSpanData | LabelRefData,
    Field(discriminator="type"),
]


class DataObj(Model):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fields: dict[FieldName, DataType] = Field(default_factory=dict, max_length=MAX_SCHEMA_FIELDS)
    kind: Literal["object"] = "object"


type Data = Annotated[DataObj | DataType, Field(discriminator="kind")]

data_adapter = TypeAdapter[Data](Data)


def validate(data: DataObj, schema: Schema) -> None:
    """
    Validate exact conformance of a persisted workflow instance.

    Pydantic has already validated each tagged elementary value. Exact
    conformance additionally requires the instance and schema to have identical
    field names and matching elementary type tags. Reference integrity,
    authorization, and staleness require database access and are intentionally
    deferred to execution preflight.
    """

    data_fields = set(data.fields)
    schema_fields = set(schema.fields)
    if data_fields != schema_fields:
        missing = sorted(schema_fields - data_fields)
        unexpected = sorted(data_fields - schema_fields)
        raise ValueError(f"Field keys mismatch; missing={missing}, unexpected={unexpected}")

    _validate_required_fields(data, schema)


def validate_compatible(data: DataObj, schema: Schema) -> None:
    """
    Validate structural compatibility with a function input schema.

    Unlike exact persisted-instance validation, data may contain additional
    fields. This lets a function declare only the fields it reads.
    """

    _validate_required_fields(data, schema)


def _validate_required_fields(data: DataObj, schema: Schema) -> None:
    for field_name, field in schema.fields.items():
        if field_name not in data.fields:
            raise ValueError(f"Field '{field_name}' not found in data fields: {list(data.fields)}")
        if data.fields[field_name].type != field.type:
            raise ValueError(f"Field '{field_name}' type mismatch: {data.fields[field_name].type} != {field.type}")


def extends(extension: SObj, base: SObj) -> bool:
    """
    Return whether extension can be used where base is required.

    Object schemas use structural subtyping, so extension may contain additional
    fields. Mutability is a capability: a mutable field can be used by a
    read-only consumer, while an immutable field cannot satisfy a consumer that
    explicitly requires mutation.
    """

    if isinstance(extension, Schema) and isinstance(base, Schema):
        for field_name, base_field in base.fields.items():
            extension_field = extension.fields.get(field_name)
            if extension_field is None or not extends(extension_field, base_field):
                return False
        return True

    if isinstance(extension, SchemaFieldBase) and isinstance(base, SchemaFieldBase):
        return extension.type == base.type and (not base.mutable or extension.mutable)

    return False
