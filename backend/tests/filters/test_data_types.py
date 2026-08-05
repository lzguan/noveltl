import uuid

import pytest
from pydantic import TypeAdapter, ValidationError

from src.filters.data_types import (
    MAX_FIELD_NAME_LENGTH,
    MAX_SCHEMA_FIELDS,
    BoolData,
    Data,
    DataObj,
    LabelRef,
    Schema,
    SObj,
    StringData,
    StringField,
    TextSpan,
    extends,
    validate,
    validate_compatible,
)


def test_schema_and_data_unions_generate_json_schemas() -> None:
    assert TypeAdapter(SObj).json_schema()
    assert TypeAdapter(Data).json_schema()


def test_schema_union_uses_string_kind_discriminator() -> None:
    adapter = TypeAdapter(SObj)

    parsed = adapter.validate_python(
        {
            "kind": "schema",
            "fields": {"word": {"kind": "field", "type": "string"}},
        }
    )

    assert parsed == Schema(fields={"word": StringField()})
    with pytest.raises(ValidationError):
        adapter.validate_python({"obj": True, "fields": {}})


def test_bool_data_parses_through_data_union() -> None:
    parsed = TypeAdapter(Data).validate_python({"obj": False, "type": "bool", "value": True})

    assert isinstance(parsed, BoolData)
    assert parsed.value is True


def test_validate_requires_exact_instance_fields() -> None:
    data = DataObj(
        fields={
            "word": StringData(type="string", value="name"),
            "extra": BoolData(type="bool", value=True),
        }
    )
    schema = Schema(fields={"word": StringField(mutable=False)})

    with pytest.raises(ValueError, match="unexpected=\\['extra'\\]"):
        validate(data, schema)


def test_validate_compatible_accepts_structural_extension() -> None:
    data = DataObj(
        fields={
            "word": StringData(type="string", value="name"),
            "extra": BoolData(type="bool", value=True),
        }
    )
    schema = Schema(fields={"word": StringField()})

    validate_compatible(data, schema)


def test_validate_rejects_missing_or_incompatible_fields() -> None:
    schema = Schema(fields={"word": StringField(mutable=False)})

    with pytest.raises(ValueError, match="missing=\\['word'\\]"):
        validate(DataObj(), schema)

    with pytest.raises(ValueError, match="type mismatch"):
        validate(DataObj(fields={"word": BoolData(type="bool", value=True)}), schema)


def test_scalar_mutability_is_opt_in() -> None:
    assert StringField().mutable is False


@pytest.mark.parametrize(
    "raw",
    [
        {"obj": False, "type": "int", "value": True},
        {"obj": False, "type": "int", "value": "12"},
        {"obj": False, "type": "float", "value": float("nan")},
        {"obj": False, "type": "float", "value": float("inf")},
    ],
)
def test_elementary_numbers_reject_coercion_and_non_finite_values(raw: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(Data).validate_python(raw)


def test_schema_rejects_invalid_field_names_and_excessive_fields() -> None:
    with pytest.raises(ValidationError):
        Schema.model_validate({"fields": {"   ": {"type": "string"}}})

    with pytest.raises(ValidationError):
        Schema.model_validate({"fields": {"x" * (MAX_FIELD_NAME_LENGTH + 1): {"type": "string"}}})

    fields = {f"field_{index}": {"type": "string"} for index in range(MAX_SCHEMA_FIELDS + 1)}
    with pytest.raises(ValidationError):
        Schema.model_validate({"fields": fields})


def test_extends_treats_mutability_as_a_capability() -> None:
    assert extends(StringField(mutable=True), StringField(mutable=False))
    assert extends(StringField(mutable=True), StringField(mutable=True))
    assert extends(StringField(mutable=False), StringField(mutable=False))
    assert not extends(StringField(mutable=False), StringField(mutable=True))


def test_object_schema_extends_structurally() -> None:
    extension = Schema(
        fields={
            "word": StringField(mutable=True),
            "extra": StringField(mutable=False),
        }
    )

    assert extends(extension, Schema(fields={"word": StringField(mutable=False)}))
    assert not extends(extension, Schema(fields={"missing": StringField(mutable=False)}))
    assert not extends(StringField(), Schema())


def test_text_span_rejects_invalid_ranges_and_extra_fields() -> None:
    chapter_id = uuid.uuid4()
    content_id = uuid.uuid4()

    with pytest.raises(ValidationError):
        TextSpan(start=2, end=1, chapter_id=chapter_id, chapter_content_id=content_id)

    with pytest.raises(ValidationError):
        TextSpan.model_validate(
            {
                "start": 0,
                "end": 1,
                "chapterId": chapter_id,
                "chapterContentId": content_id,
                "unexpected": True,
            }
        )


def test_label_reference_rejects_embedded_offsets() -> None:
    with pytest.raises(ValidationError):
        LabelRef.model_validate(
            {
                "chapterId": uuid.uuid4(),
                "chapterContentId": uuid.uuid4(),
                "labelId": uuid.uuid4(),
                "labelDataId": uuid.uuid4(),
                "labelGroupId": uuid.uuid4(),
                "start": 0,
                "end": 1,
            }
        )
