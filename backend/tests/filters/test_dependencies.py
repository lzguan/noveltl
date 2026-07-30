from src.filters.data_types import LabelRefField, Schema, TextSpanField
from src.filters.dependencies import ResolvedResourceDependency, resolve_dependencies
from src.filters.functions import (
    Call,
    Construct,
    Get,
    ProjectToSpan,
    ResourceDependency,
    ScoreOf,
    TextAround,
    TextOf,
    WordOf,
)


def test_text_functions_declare_discriminated_resource_dependencies() -> None:
    expected = ResourceDependency(
        dependency_type="resource",
        resource="chapter_content_text",
        argument_index=0,
    )

    assert TextOf().dependencies == (expected,)
    assert TextAround(slack=20).dependencies == (expected,)


def test_label_functions_resolve_label_resources() -> None:
    expected = ResourceDependency(
        dependency_type="resource",
        resource="label",
        argument_index=0,
    )
    input_schema = Schema(fields={"label": LabelRefField()})
    word = Call(
        input_schema=input_schema,
        function=WordOf(),
        arguments=(Get(field_name="label", type="labelRef"),),
    )

    assert ScoreOf().dependencies == (expected,)
    assert WordOf().dependencies == (expected,)
    assert resolve_dependencies(word) == (
        ResolvedResourceDependency(
            resource="label",
            argument_index=0,
            key_path=("label",),
        ),
    )


def test_resolve_direct_elementary_argument_dependency() -> None:
    assert resolve_dependencies(TextOf()) == (
        ResolvedResourceDependency(
            resource="chapter_content_text",
            argument_index=0,
            key_path=(),
        ),
    )


def test_resolve_dependency_through_call_and_projection() -> None:
    input_schema = Schema(fields={"label": LabelRefField()})
    span = Call(
        input_schema=input_schema,
        function=ProjectToSpan(),
        arguments=(Get(field_name="label", type="labelRef"),),
    )
    text = Call(
        input_schema=input_schema,
        function=TextOf(),
        arguments=(span,),
    )

    assert resolve_dependencies(text) == (
        ResolvedResourceDependency(
            resource="chapter_content_text",
            argument_index=0,
            key_path=("label",),
        ),
        ResolvedResourceDependency(
            resource="label",
            argument_index=0,
            key_path=("label",),
        ),
    )


def test_resolve_composite_dependencies_deduplicates_and_orders() -> None:
    input_schema = Schema(
        fields={
            "secondSpan": TextSpanField(),
            "firstSpan": TextSpanField(),
        }
    )

    def text_of(field_name: str) -> Call:
        return Call(
            input_schema=input_schema,
            function=TextOf(),
            arguments=(Get(field_name=field_name, type="textSpan"),),
        )

    function = Construct(
        input_schema=input_schema,
        fields={
            "firstText": text_of("firstSpan"),
            "firstTextAgain": text_of("firstSpan"),
            "secondText": text_of("secondSpan"),
        },
    )

    assert resolve_dependencies(function) == (
        ResolvedResourceDependency(
            resource="chapter_content_text",
            argument_index=0,
            key_path=("firstSpan",),
        ),
        ResolvedResourceDependency(
            resource="chapter_content_text",
            argument_index=0,
            key_path=("secondSpan",),
        ),
    )
