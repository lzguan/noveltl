import uuid

from src.filters.compilers.python import PythonCompiler
from src.filters.context.python import PythonExecutionContext, PythonLabelResource
from src.filters.data_types import (
    BoolData,
    DataObj,
    FloatData,
    FloatField,
    IntData,
    IntField,
    LabelRef,
    LabelRefData,
    Schema,
    StringData,
    StringField,
    TextSpan,
    TextSpanData,
)
from src.filters.functions import (
    And,
    Call,
    Compare,
    Construct,
    Extend,
    Get,
    LiteralBool,
    LiteralFloat,
    LiteralString,
    ProjectToSpan,
    Rename,
    RenamePair,
)


class _NoResourceContext:
    def get_chapter_content(self, chapter_content_id: uuid.UUID) -> str:
        raise AssertionError(f"Unexpected chapter content dependency: {chapter_content_id}")

    def load_resources(self, resource_ids: object) -> None:
        raise AssertionError(f"Unexpected resource preload: {resource_ids}")

    def get_label(self, label_id: uuid.UUID) -> PythonLabelResource:
        raise AssertionError(f"Unexpected label dependency: {label_id}")


ctx: PythonExecutionContext = _NoResourceContext()


def test_compiled_function_retains_signature_and_executes() -> None:
    compiler = PythonCompiler()
    literal = compiler.compile(LiteralString(value="constant"))

    assert literal.signature == LiteralString(value="constant").signature
    assert literal((), ctx) == StringData(value="constant")


def test_compile_call_evaluates_composed_comparison() -> None:
    schema = Schema(fields={"score": FloatField()})
    function = Call(
        input_schema=schema,
        function=Compare(type="float", op="lt"),
        arguments=(
            Get(field_name="score", type="float"),
            LiteralFloat(value=0.5),
        ),
    )
    compiled = PythonCompiler().compile(function)

    assert compiled((DataObj(fields={"score": FloatData(value=0.25)}),), ctx) == BoolData(value=True)
    assert compiled((DataObj(fields={"score": FloatData(value=0.75)}),), ctx) == BoolData(value=False)


def test_compile_multi_argument_primitive() -> None:
    compiled = PythonCompiler().compile(And(num=2))

    assert compiled((BoolData(value=True), BoolData(value=False)), ctx) == BoolData(value=False)


def test_compile_rename_construct_and_extend() -> None:
    input_schema = Schema(
        fields={
            "word": StringField(),
            "count": IntField(),
        }
    )
    data = DataObj(
        fields={
            "word": StringData(value="name"),
            "count": IntData(value=2),
        }
    )
    compiler = PythonCompiler()

    rename = compiler.compile(
        Rename(
            original_schema=input_schema,
            rename_pairs=(RenamePair(old_name="word", new_name="term"),),
        )
    )
    assert rename((data,), ctx) == DataObj(
        fields={
            "term": StringData(value="name"),
            "count": IntData(value=2),
        }
    )

    construct = compiler.compile(
        Construct(
            input_schema=input_schema,
            fields={
                "term": Get(field_name="word", type="string"),
                "decision": LiteralString(value="pending", mutable=True),
            },
        )
    )
    assert construct((data,), ctx) == DataObj(
        fields={
            "term": StringData(value="name"),
            "decision": StringData(value="pending"),
        }
    )

    extend = compiler.compile(
        Extend(
            input_schema=input_schema,
            fields={"accepted": LiteralBool(value=False, mutable=True)},
        )
    )
    assert extend((data,), ctx) == DataObj(
        fields={
            "word": StringData(value="name"),
            "count": IntData(value=2),
            "accepted": BoolData(value=False),
        }
    )


def test_project_to_span_drops_label_only_fields() -> None:
    chapter_content_id = uuid.uuid4()
    label = LabelRef(
        start=1,
        end=4,
        chapter_content_id=chapter_content_id,
        label_id=uuid.uuid4(),
        label_data_id=uuid.uuid4(),
        label_group_id=uuid.uuid4(),
    )

    result = PythonCompiler().compile(ProjectToSpan())((LabelRefData(value=label),), ctx)

    assert isinstance(result, TextSpanData)
    assert result == TextSpanData(value=TextSpan(start=1, end=4, chapter_content_id=chapter_content_id))
    assert type(result.value) is TextSpan
