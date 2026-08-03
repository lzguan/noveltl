import pytest
from pydantic import TypeAdapter, ValidationError

from src.filters.data_types import BoolField, FloatField, IntField, Schema, StringField, TextSpanField
from src.filters.functions import (
    MAX_FUNCTION_ARITY,
    MAX_LITERAL_STRING_LENGTH,
    MAX_RENAME_PAIRS,
    Add,
    And,
    Call,
    Ceil,
    Compare,
    Concat,
    Construct,
    Contains,
    Extend,
    Floor,
    FunctionType,
    Get,
    If,
    LiteralBool,
    LiteralFloat,
    LiteralString,
    Maximum,
    Minimum,
    Not,
    ProjectToSpan,
    Rename,
    Round,
    Subtract,
    ToFloat,
)


def test_function_union_generates_json_schema_and_parses() -> None:
    adapter = TypeAdapter(FunctionType)

    assert adapter.json_schema()
    parsed = adapter.validate_python({"name": "literalBool", "value": True})
    assert isinstance(parsed.signature.output, BoolField)


def test_signature_is_computed_and_cannot_be_supplied() -> None:
    literal = LiteralString(value="value", mutable=False)

    assert isinstance(literal.signature.output, StringField)
    assert literal.signature.output.mutable is False
    assert literal.model_dump()["signature"]["output"]["mutable"] is False

    with pytest.raises(ValidationError):
        LiteralString.model_validate(
            {
                "value": "value",
                "signature": {
                    "args": [],
                    "output": {"obj": False, "type": "int", "mutable": False},
                },
            }
        )


def test_literals_default_to_immutable_and_reject_invalid_values() -> None:
    assert LiteralString(value="value").mutable is False

    with pytest.raises(ValidationError):
        LiteralString(value="x" * (MAX_LITERAL_STRING_LENGTH + 1))

    with pytest.raises(ValidationError):
        LiteralFloat(value=float("nan"))


def test_get_signature_tracks_requested_type_and_mutability() -> None:
    getter = Get(field_name="word", type="string", mutable=True)

    assert getter.signature.args == (Schema(fields={"word": StringField(mutable=True)}),)
    assert getter.signature.output == StringField(mutable=True)

    with pytest.raises(ValidationError, match="cannot be mutable"):
        Get(field_name="label", type="labelRef", mutable=True)


def test_compare_signature_and_boolean_operator_validation() -> None:
    comparison = Compare(type="int", op="ge")
    argument = IntField(mutable=False)

    assert comparison.signature.args == (argument, argument)
    assert comparison.signature.output == BoolField(mutable=False)

    with pytest.raises(ValidationError, match="Boolean comparisons"):
        Compare(type="bool", op="lt")


@pytest.mark.parametrize("function_type", ["int", "float"])
def test_numeric_signatures(function_type: str) -> None:
    field = IntField() if function_type == "int" else FloatField()

    for function in (
        Add.model_validate({"type": function_type, "num": 3}),
        Maximum.model_validate({"type": function_type, "num": 3}),
        Minimum.model_validate({"type": function_type, "num": 3}),
    ):
        assert function.signature.args == (field, field, field)
        assert function.signature.output == field

    assert Subtract.model_validate({"type": function_type}).signature.args == (field, field)


@pytest.mark.parametrize("function", [Add, Maximum, Minimum, Concat])
def test_variadic_functions_validate_arity(function: type[Add | Maximum | Minimum | Concat]) -> None:
    values: dict[str, object] = {"num": 1}
    if function is not Concat:
        values["type"] = "int"
    assert len(function.model_validate(values).signature.args) == 1

    with pytest.raises(ValidationError):
        function.model_validate({**values, "num": 0})

    with pytest.raises(ValidationError):
        function.model_validate({**values, "num": MAX_FUNCTION_ARITY + 1})


def test_string_and_numeric_conversion_signatures() -> None:
    string = StringField()

    assert Concat(num=3).signature.args == (string, string, string)
    assert Concat(num=3).signature.output == string
    assert Contains().signature.args == (string, string)
    assert Contains().signature.output == BoolField()
    assert ToFloat().signature.args == (IntField(),)
    assert ToFloat().signature.output == FloatField()

    for function in (Floor(), Ceil(), Round()):
        assert function.signature.args == (FloatField(),)
        assert function.signature.output == IntField()


def test_project_to_span_signature() -> None:
    assert ProjectToSpan().signature.output == TextSpanField()


def test_if_parses_and_round_trips_with_elementary_schemas() -> None:
    definition = {
        "name": "if",
        "inputSchema": {"obj": False, "type": "bool"},
        "outputSchema": {"obj": False, "type": "bool"},
        "condition": {"name": "not"},
        "thenBranch": {"name": "not"},
        "elseBranch": {"name": "not"},
    }

    parsed = TypeAdapter(FunctionType).validate_python(definition)

    assert isinstance(parsed, If)
    assert parsed.signature.args == (BoolField(),)
    assert parsed.signature.output == BoolField()
    assert (
        TypeAdapter(FunctionType).validate_python(parsed.model_dump(exclude_computed_fields=True, by_alias=True))
        == parsed
    )


def test_if_signature_supports_record_schemas() -> None:
    input_schema = Schema(
        fields={
            "condition": BoolField(),
            "then": StringField(),
            "else": StringField(),
        }
    )
    function = If(
        input_schema=input_schema,
        output_schema=StringField(),
        condition=Get(field_name="condition", type="bool"),
        then_branch=Get(field_name="then", type="string"),
        else_branch=Get(field_name="else", type="string"),
    )

    assert function.signature.args == (input_schema,)
    assert function.signature.output == StringField()


@pytest.mark.parametrize(
    ("condition", "message"),
    [
        (Get(field_name="value", type="int"), "return a boolean"),
        (Get(field_name="value", type="bool", mutable=True), "return a boolean"),
        (LiteralBool(value=True), "accept exactly one argument"),
        (And(num=2), "accept exactly one argument"),
    ],
)
def test_if_rejects_invalid_conditions(condition: object, message: str) -> None:
    input_schema = Schema(
        fields={
            "value": BoolField(mutable=True) if isinstance(condition, Get) and condition.type == "bool" else IntField()
        }
    )

    with pytest.raises(ValidationError, match=message):
        If.model_validate(
            {
                "inputSchema": input_schema,
                "outputSchema": IntField(),
                "condition": condition,
                "thenBranch": Get(field_name="value", type="int"),
                "elseBranch": Get(field_name="value", type="int"),
            }
        )


@pytest.mark.parametrize(
    ("then_branch", "else_branch", "message"),
    [
        (LiteralBool(value=True), Not(), "Then branch function must accept exactly one argument"),
        (Not(), LiteralBool(value=True), "Else branch function must accept exactly one argument"),
        (And(num=2), Not(), "Then branch function must accept exactly one argument"),
        (Not(), And(num=2), "Else branch function must accept exactly one argument"),
    ],
)
def test_if_rejects_non_unary_branches(
    then_branch: object,
    else_branch: object,
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        If.model_validate(
            {
                "inputSchema": BoolField(),
                "outputSchema": BoolField(),
                "condition": Not(),
                "thenBranch": then_branch,
                "elseBranch": else_branch,
            }
        )


@pytest.mark.parametrize(
    ("input_schema", "condition", "then_branch", "else_branch", "message"),
    [
        (IntField(), Not(), ToFloat(), ToFloat(), "Condition function cannot consume"),
        (BoolField(), Not(), ToFloat(), Not(), "Then branch function cannot consume"),
        (BoolField(), Not(), Not(), ToFloat(), "Else branch function cannot consume"),
    ],
)
def test_if_rejects_children_incompatible_with_input(
    input_schema: object,
    condition: object,
    then_branch: object,
    else_branch: object,
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        If.model_validate(
            {
                "inputSchema": input_schema,
                "outputSchema": BoolField(),
                "condition": condition,
                "thenBranch": then_branch,
                "elseBranch": else_branch,
            }
        )


@pytest.mark.parametrize(
    ("then_branch", "else_branch", "message"),
    [
        (
            Get(field_name="integer", type="int"),
            Get(field_name="boolean", type="bool"),
            "Then branch output is incompatible",
        ),
        (
            Get(field_name="boolean", type="bool"),
            Get(field_name="integer", type="int"),
            "Else branch output is incompatible",
        ),
    ],
)
def test_if_rejects_branch_outputs_incompatible_with_declared_output(
    then_branch: object,
    else_branch: object,
    message: str,
) -> None:
    input_schema = Schema(fields={"boolean": BoolField(), "integer": IntField()})

    with pytest.raises(ValidationError, match=message):
        If.model_validate(
            {
                "inputSchema": input_schema,
                "outputSchema": BoolField(),
                "condition": Get(field_name="boolean", type="bool"),
                "thenBranch": then_branch,
                "elseBranch": else_branch,
            }
        )


def test_rename_preserves_unrenamed_fields_and_supports_swaps() -> None:
    rename = Rename.model_validate(
        {
            "renamePairs": [
                {"oldName": "word", "newName": "count"},
                {"oldName": "count", "newName": "word"},
            ],
            "originalSchema": {
                "fields": {
                    "word": {"type": "string", "mutable": False},
                    "count": {"type": "int", "mutable": False},
                    "untouched": {"type": "bool", "mutable": False},
                }
            },
        }
    )

    assert rename.signature.output == Schema(
        fields={
            "word": IntField(mutable=False),
            "count": StringField(mutable=False),
            "untouched": BoolField(mutable=False),
        }
    )


@pytest.mark.parametrize(
    "rename_pairs, message",
    [
        ([{"oldName": "missing", "newName": "renamed"}], "does not exist"),
        (
            [
                {"oldName": "word", "newName": "renamed"},
                {"oldName": "word", "newName": "another"},
            ],
            "duplicated",
        ),
        ([{"oldName": "word", "newName": "untouched"}], "conflict"),
    ],
)
def test_rename_rejects_invalid_pairs(rename_pairs: list[dict[str, str]], message: str) -> None:
    original_schema = Schema(
        fields={
            "word": StringField(),
            "untouched": BoolField(),
        }
    )

    with pytest.raises(ValidationError, match=message):
        Rename(rename_pairs=rename_pairs, original_schema=original_schema)


def test_logical_functions_require_at_least_one_argument() -> None:
    with pytest.raises(ValidationError):
        And.model_validate({"num": 0})

    with pytest.raises(ValidationError):
        And.model_validate({"num": MAX_FUNCTION_ARITY + 1})

    with pytest.raises(ValidationError):
        And.model_validate({"num": "3"})

    assert len(And(num=3).signature.args) == 3


def test_rename_limits_pair_count() -> None:
    rename_pairs = [
        {"oldName": f"field_{index}", "newName": f"renamed_{index}"} for index in range(MAX_RENAME_PAIRS + 1)
    ]
    original_fields = {f"field_{index}": {"type": "string"} for index in range(MAX_RENAME_PAIRS + 1)}

    with pytest.raises(ValidationError):
        Rename.model_validate(
            {
                "renamePairs": rename_pairs,
                "originalSchema": {"fields": original_fields},
            }
        )


def test_construct_builds_object_schema_from_field_functions() -> None:
    input_schema = Schema(
        fields={
            "word": StringField(),
            "count": IntField(),
            "unused": BoolField(),
        }
    )
    construct = Construct(
        input_schema=input_schema,
        fields={
            "selectedWord": Get(field_name="word", type="string"),
            "selectedCount": Get(field_name="count", type="int"),
        },
    )

    assert construct.signature.args == (input_schema,)
    assert construct.signature.output == Schema(
        fields={
            "selectedWord": StringField(),
            "selectedCount": IntField(),
        }
    )


def test_construct_parses_through_function_union() -> None:
    parsed = TypeAdapter(FunctionType).validate_python(
        {
            "name": "construct",
            "inputSchema": {
                "fields": {
                    "word": {"type": "string"},
                    "count": {"type": "int"},
                }
            },
            "fields": {
                "selected": {
                    "name": "get",
                    "fieldName": "word",
                    "type": "string",
                }
            },
        }
    )

    assert isinstance(parsed, Construct)
    assert parsed.signature.output == Schema(fields={"selected": StringField()})


@pytest.mark.parametrize(
    "function, message",
    [
        (Compare(type="string", op="eq"), "zero or one unbound argument"),
        (ProjectToSpan(), "cannot consume"),
    ],
)
def test_construct_rejects_incompatible_field_functions(function: object, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Construct.model_validate(
            {
                "inputSchema": {"fields": {"word": {"type": "string"}}},
                "fields": {"result": function},
            }
        )


def test_construct_rejects_object_outputs() -> None:
    input_schema = Schema(fields={"word": StringField()})
    rename = Rename(
        rename_pairs=({"oldName": "word", "newName": "renamed"},),
        original_schema=input_schema,
    )

    with pytest.raises(ValidationError, match="elementary data type"):
        Construct(input_schema=input_schema, fields={"result": rename})


def test_construct_rejects_empty_field_map() -> None:
    with pytest.raises(ValidationError):
        Construct.model_validate({"inputSchema": {"fields": {}}, "fields": {}})


def test_construct_lifts_literal_fields() -> None:
    construct = Construct(
        input_schema=Schema(fields={"word": StringField()}),
        fields={"classification": LiteralString(value="name")},
    )

    assert construct.signature.output == Schema(fields={"classification": StringField()})


def test_call_binds_shared_input_expressions() -> None:
    input_schema = Schema(fields={"score": FloatField()})
    call = Call(
        input_schema=input_schema,
        function=Compare(type="float", op="lt"),
        arguments=(
            Get(field_name="score", type="float"),
            LiteralFloat(value=0.5),
        ),
    )

    assert call.signature.args == (input_schema,)
    assert call.signature.output == BoolField()


def test_nested_call_round_trips_through_function_union() -> None:
    input_schema = Schema(fields={"score": FloatField()})
    comparison = Call(
        input_schema=input_schema,
        function=Compare(type="float", op="lt"),
        arguments=(
            Get(field_name="score", type="float"),
            LiteralFloat(value=0.5),
        ),
    )
    expression = Call(
        input_schema=input_schema,
        function=And(num=2),
        arguments=(
            comparison,
            LiteralBool(value=True),
        ),
    )
    definition = expression.model_dump(exclude_computed_fields=True, by_alias=True)

    assert TypeAdapter(FunctionType).validate_python(definition) == expression


def test_call_rejects_wrong_argument_count_and_types() -> None:
    input_schema = Schema(fields={"score": FloatField()})

    with pytest.raises(ValidationError, match="requires 2 arguments"):
        Call(
            input_schema=input_schema,
            function=Compare(type="float", op="lt"),
            arguments=(Get(field_name="score", type="float"),),
        )

    with pytest.raises(ValidationError, match="incompatible"):
        Call(
            input_schema=input_schema,
            function=Compare(type="float", op="lt"),
            arguments=(
                Get(field_name="score", type="float"),
                LiteralString(value="not a float"),
            ),
        )


def test_extend_preserves_input_and_adds_derived_fields() -> None:
    input_schema = Schema(fields={"score": FloatField()})
    comparison = Call(
        input_schema=input_schema,
        function=Compare(type="float", op="lt"),
        arguments=(
            Get(field_name="score", type="float"),
            LiteralFloat(value=0.5),
        ),
    )
    extend = Extend(
        input_schema=input_schema,
        fields={
            "lowScore": comparison,
            "review": LiteralString(value="pending", mutable=True),
        },
    )

    assert extend.signature.output == Schema(
        fields={
            "score": FloatField(),
            "lowScore": BoolField(),
            "review": StringField(mutable=True),
        }
    )


def test_extend_rejects_field_collisions() -> None:
    input_schema = Schema(fields={"score": FloatField()})

    with pytest.raises(ValidationError, match="conflict"):
        Extend(
            input_schema=input_schema,
            fields={"score": LiteralFloat(value=0.5)},
        )
