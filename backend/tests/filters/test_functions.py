import pytest
from pydantic import TypeAdapter, ValidationError

from src.filters.data_types import BoolField, IntField, Schema, StringField, TextSpanField
from src.filters.functions import (
    MAX_FUNCTION_ARITY,
    MAX_LITERAL_STRING_LENGTH,
    MAX_RENAME_PAIRS,
    And,
    Compare,
    Construct,
    FunctionType,
    Get,
    LiteralFloat,
    LiteralString,
    ProjectToSpan,
    Rename,
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
    comparison = Compare(field_name="count", type="int", op="ge")
    argument = Schema(fields={"count": IntField(mutable=False)})

    assert comparison.signature.args == (argument, argument)
    assert comparison.signature.output == BoolField(mutable=False)

    with pytest.raises(ValidationError, match="Boolean comparisons"):
        Compare(field_name="flag", type="bool", op="lt")


def test_project_to_span_signature() -> None:
    assert ProjectToSpan().signature.output == TextSpanField()


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
        (LiteralString(value="constant"), "exactly one argument"),
        (Compare(field_name="word", type="string", op="eq"), "exactly one argument"),
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
