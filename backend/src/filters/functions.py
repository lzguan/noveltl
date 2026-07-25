from __future__ import annotations

from abc import abstractmethod
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, TypeAdapter, computed_field, model_validator

from src.filters.data_types import (
    MAX_SCHEMA_FIELDS,
    BooleanValue,
    BoolField,
    ElementaryTypeName,
    FieldName,
    FloatField,
    FloatValue,
    IntegerValue,
    IntField,
    LabelRefField,
    Schema,
    SchemaField,
    SchemaFieldBase,
    SObj,
    StringField,
    StringValue,
    TextSpanField,
    extends,
)
from src.schemas import Model

# These are per-node parse-time limits. When recursive function expressions are
# introduced, semantic validation must also bound total nodes and nesting depth.
MAX_FUNCTION_ARITY = 256
MAX_LITERAL_STRING_LENGTH = 10_000
MAX_RENAME_PAIRS = 128


class Signature(Model):
    """The input and output schemas of a function."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    args: tuple[SObj, ...] = ()
    output: SObj


class Function(Model):
    """Base model for a persisted function description."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @computed_field
    @property
    @abstractmethod
    def signature(self) -> Signature:
        """The input and output schemas of the function."""
        ...

    name: str


def discriminate_type(type_name: ElementaryTypeName, *, mutable: bool = False) -> SchemaField:
    """Construct a schema field for an elementary type."""

    if type_name == "string":
        return StringField(mutable=mutable)
    if type_name == "int":
        return IntField(mutable=mutable)
    if type_name == "float":
        return FloatField(mutable=mutable)
    if type_name == "bool":
        return BoolField(mutable=mutable)
    if type_name == "labelRef":
        if mutable:
            raise ValueError("Label references cannot be mutable.")
        return LabelRefField()
    if type_name == "textSpan":
        if mutable:
            raise ValueError("Text spans cannot be mutable.")
        return TextSpanField()
    raise ValueError(f"Unsupported elementary type: {type_name}")


class LiteralString(Function):
    name: Literal["literalString"] = "literalString"
    value: StringValue = Field(max_length=MAX_LITERAL_STRING_LENGTH)
    mutable: bool = False

    @computed_field
    @property
    def signature(self) -> Signature:
        return Signature(output=StringField(mutable=self.mutable))


class LiteralInt(Function):
    name: Literal["literalInt"] = "literalInt"
    value: IntegerValue
    mutable: bool = False

    @computed_field
    @property
    def signature(self) -> Signature:
        return Signature(output=IntField(mutable=self.mutable))


class LiteralFloat(Function):
    name: Literal["literalFloat"] = "literalFloat"
    value: FloatValue
    mutable: bool = False

    @computed_field
    @property
    def signature(self) -> Signature:
        return Signature(output=FloatField(mutable=self.mutable))


class LiteralBool(Function):
    name: Literal["literalBool"] = "literalBool"
    value: BooleanValue
    mutable: bool = False

    @computed_field
    @property
    def signature(self) -> Signature:
        return Signature(output=BoolField(mutable=self.mutable))


class Get(Function):
    name: Literal["get"] = "get"
    field_name: FieldName
    type: ElementaryTypeName
    mutable: bool = False

    @model_validator(mode="after")
    def validate_mutability(self) -> Get:
        discriminate_type(self.type, mutable=self.mutable)
        return self

    @computed_field
    @property
    def signature(self) -> Signature:
        field = discriminate_type(self.type, mutable=self.mutable)
        return Signature(
            args=(Schema(fields={self.field_name: field}),),
            output=field,
        )


class Compare(Function):
    name: Literal["compare"] = "compare"
    type: Literal["string", "int", "float", "bool"]
    op: Literal["eq", "ne", "lt", "le", "gt", "ge"]

    @model_validator(mode="after")
    def validate_operator(self) -> Compare:
        if self.type == "bool" and self.op not in ("eq", "ne"):
            raise ValueError("Boolean comparisons support only 'eq' and 'ne'.")
        return self

    @computed_field
    @property
    def signature(self) -> Signature:
        field = discriminate_type(self.type)
        return Signature(
            args=(field, field),
            output=BoolField(mutable=False),
        )


class ProjectToSpan(Function):
    name: Literal["projectToSpan"] = "projectToSpan"

    @computed_field
    @property
    def signature(self) -> Signature:
        return Signature(
            args=(LabelRefField(),),
            output=TextSpanField(),
        )


class RenamePair(Model):
    """A simultaneous field rename."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    old_name: FieldName
    new_name: FieldName


class Rename(Function):
    name: Literal["rename"] = "rename"
    rename_pairs: tuple[RenamePair, ...] = Field(min_length=1, max_length=MAX_RENAME_PAIRS)
    original_schema: Schema

    @model_validator(mode="after")
    def validate_rename_pairs(self) -> Rename:
        old_names: set[str] = set()
        new_names: set[str] = set()

        for pair in self.rename_pairs:
            if pair.old_name not in self.original_schema.fields:
                raise ValueError(f"Old name '{pair.old_name}' does not exist in the original schema.")
            if pair.old_name in old_names:
                raise ValueError(f"Old name '{pair.old_name}' is duplicated in the rename pairs.")
            if pair.new_name in new_names:
                raise ValueError(f"New name '{pair.new_name}' is duplicated in the rename pairs.")
            old_names.add(pair.old_name)
            new_names.add(pair.new_name)

        unrenamed_names = set(self.original_schema.fields) - old_names
        collisions = new_names & unrenamed_names
        if collisions:
            names = ", ".join(sorted(collisions))
            raise ValueError(f"Renamed fields conflict with existing fields: {names}.")

        return self

    @computed_field
    @property
    def signature(self) -> Signature:
        renamed_fields = dict(self.original_schema.fields)
        moved_fields = {pair.new_name: renamed_fields.pop(pair.old_name) for pair in self.rename_pairs}
        renamed_fields.update(moved_fields)
        return Signature(
            args=(self.original_schema,),
            output=Schema(fields=renamed_fields),
        )


class And(Function):
    name: Literal["and"] = "and"
    num: IntegerValue = Field(ge=1, le=MAX_FUNCTION_ARITY)

    @computed_field
    @property
    def signature(self) -> Signature:
        return Signature(
            args=tuple(BoolField(mutable=False) for _ in range(self.num)),
            output=BoolField(mutable=False),
        )


class Or(Function):
    name: Literal["or"] = "or"
    num: IntegerValue = Field(ge=1, le=MAX_FUNCTION_ARITY)

    @computed_field
    @property
    def signature(self) -> Signature:
        return Signature(
            args=tuple(BoolField(mutable=False) for _ in range(self.num)),
            output=BoolField(mutable=False),
        )


class Not(Function):
    name: Literal["not"] = "not"

    @computed_field
    @property
    def signature(self) -> Signature:
        return Signature(
            args=(BoolField(mutable=False),),
            output=BoolField(mutable=False),
        )


def output_when_called_on(function: Function, input_schema: Schema) -> SObj:
    """
    Return the output of calling function in an object-schema environment.

    Nullary functions ignore the environment. Unary functions may consume it
    when the environment structurally extends their required input. Functions
    with multiple unbound arguments must first be bound through Call.
    """

    signature = function.signature
    if len(signature.args) == 0:
        return signature.output
    if len(signature.args) != 1:
        raise ValueError(f"Function must accept zero or one unbound argument; received {len(signature.args)}.")
    if not extends(input_schema, signature.args[0]):
        raise ValueError("Function cannot consume the provided input schema.")
    return signature.output


class Construct(Function):
    """
    Build an object by evaluating several elementary-output functions against
    the same input object.
    """

    name: Literal["construct"] = "construct"
    input_schema: Schema
    fields: dict[FieldName, FunctionType] = Field(min_length=1, max_length=MAX_SCHEMA_FIELDS)

    @model_validator(mode="after")
    def validate_field_functions(self) -> Construct:
        for field_name, function in self.fields.items():
            try:
                output = output_when_called_on(function, self.input_schema)
            except ValueError as exc:
                raise ValueError(f"Invalid function for field '{field_name}': {exc}") from exc
            if not isinstance(output, SchemaFieldBase):
                raise ValueError(f"Function for field '{field_name}' must return an elementary data type.")

        return self

    @computed_field
    @property
    def signature(self) -> Signature:
        return Signature(
            args=(self.input_schema,),
            output=Schema(
                fields={
                    field_name: output
                    for field_name, function in self.fields.items()
                    if isinstance((output := output_when_called_on(function, self.input_schema)), SchemaFieldBase)
                }
            ),
        )


class Extend(Function):
    """Preserve an input object and add fields derived from that object."""

    name: Literal["extend"] = "extend"
    input_schema: Schema
    fields: dict[FieldName, FunctionType] = Field(min_length=1, max_length=MAX_SCHEMA_FIELDS)

    @model_validator(mode="after")
    def validate_field_functions(self) -> Extend:
        collisions = set(self.input_schema.fields) & set(self.fields)
        if collisions:
            names = ", ".join(sorted(collisions))
            raise ValueError(f"Extended fields conflict with existing fields: {names}.")
        if len(self.input_schema.fields) + len(self.fields) > MAX_SCHEMA_FIELDS:
            raise ValueError(f"Extended schema cannot contain more than {MAX_SCHEMA_FIELDS} fields.")

        for field_name, function in self.fields.items():
            try:
                output = output_when_called_on(function, self.input_schema)
            except ValueError as exc:
                raise ValueError(f"Invalid function for field '{field_name}': {exc}") from exc
            if not isinstance(output, SchemaFieldBase):
                raise ValueError(f"Function for field '{field_name}' must return an elementary data type.")

        return self

    @computed_field
    @property
    def signature(self) -> Signature:
        fields = dict(self.input_schema.fields)
        fields.update(
            {
                field_name: output
                for field_name, function in self.fields.items()
                if isinstance((output := output_when_called_on(function, self.input_schema)), SchemaFieldBase)
            }
        )
        return Signature(
            args=(self.input_schema,),
            output=Schema(fields=fields),
        )


class Call(Function):
    """Bind a function's arguments to expressions sharing one input schema."""

    name: Literal["call"] = "call"
    input_schema: Schema
    function: FunctionType
    arguments: tuple[FunctionType, ...] = Field(max_length=MAX_FUNCTION_ARITY)

    @model_validator(mode="after")
    def validate_arguments(self) -> Call:
        parameters = self.function.signature.args
        if len(self.arguments) != len(parameters):
            raise ValueError(f"Function requires {len(parameters)} arguments; received {len(self.arguments)}.")

        for index, (argument, parameter) in enumerate(zip(self.arguments, parameters, strict=True)):
            try:
                argument_output = output_when_called_on(argument, self.input_schema)
            except ValueError as exc:
                raise ValueError(f"Invalid argument {index}: {exc}") from exc
            if not extends(argument_output, parameter):
                raise ValueError(f"Argument {index} output is incompatible with the function parameter.")

        return self

    @computed_field
    @property
    def signature(self) -> Signature:
        return Signature(
            args=(self.input_schema,),
            output=self.function.signature.output,
        )


class Custom(Function):
    name: Literal["custom"] = "custom"
    custom_name: str
    root: FunctionType

    @computed_field
    @property
    def signature(self) -> Signature:
        return self.root.signature


type FunctionType = Annotated[
    LiteralString
    | LiteralInt
    | LiteralFloat
    | LiteralBool
    | Get
    | Compare
    | ProjectToSpan
    | Rename
    | And
    | Or
    | Not
    | Construct
    | Extend
    | Call
    | Custom,
    Field(discriminator="name"),
]

Construct.model_rebuild()
Extend.model_rebuild()
Call.model_rebuild()
Custom.model_rebuild()

function_adapter = TypeAdapter[FunctionType](FunctionType)
