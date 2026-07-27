from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, assert_never, cast

from src.filters.data_types import (
    BoolData,
    Data,
    DataObj,
    DataType,
    FloatData,
    IntData,
    LabelRefData,
    StringData,
    TextSpan,
    TextSpanData,
)
from src.filters.functions import (
    And,
    Call,
    Compare,
    Construct,
    Extend,
    FunctionType,
    Get,
    LiteralBool,
    LiteralFloat,
    LiteralInt,
    LiteralString,
    Not,
    Or,
    ProjectToSpan,
    Rename,
    Signature,
)

type PythonExecutable = Callable[[tuple[Data, ...]], Data]


@dataclass(frozen=True, slots=True)
class CompiledPythonFunction:
    """A function AST compiled to a validated in-memory Python callable."""

    signature: Signature
    executable: PythonExecutable

    def __call__(self, arguments: tuple[Data, ...]) -> Data:
        return self.executable(arguments)


def _evaluate_in_environment(function: CompiledPythonFunction, environment: tuple[Data, ...]) -> Data:
    """
    Evaluate a nullary or unary expression in a shared object environment.

    Nullary expressions, such as literals, ignore the environment. Unary
    expressions consume it. Function model validation prevents unbound
    multi-argument functions from appearing in these expression positions.
    """

    if len(function.signature.args) == 0:
        return function(())
    return function(environment)


def _compare_values(left: Any, right: Any, operation: str) -> bool:
    if operation == "eq":
        return left == right
    if operation == "ne":
        return left != right
    if operation == "lt":
        return left < right
    if operation == "le":
        return left <= right
    if operation == "gt":
        return left > right
    if operation == "ge":
        return left >= right
    raise ValueError(f"Unsupported comparison operation: {operation}")


class PythonCompiler:
    """Compile persisted function AST nodes to in-memory Python functions."""

    def compile(self, function: FunctionType) -> CompiledPythonFunction:
        if isinstance(function, Get):

            def get(arguments: tuple[Data, ...]) -> Data:
                data = cast(DataObj, arguments[0])
                return data.fields[function.field_name]

            executable = get

        elif isinstance(function, Compare):

            def compare(arguments: tuple[Data, ...]) -> Data:
                left = cast(DataType, arguments[0])
                right = cast(DataType, arguments[1])
                return BoolData(value=_compare_values(left.value, right.value, function.op))

            executable = compare

        elif isinstance(function, Not):

            def not_fn(arguments: tuple[Data, ...]) -> Data:
                data = cast(BoolData, arguments[0])
                return BoolData(value=not data.value)

            executable = not_fn

        elif isinstance(function, And):

            def and_fn(arguments: tuple[Data, ...]) -> Data:
                for data in arguments:
                    if not cast(BoolData, data).value:
                        return BoolData(value=False)
                return BoolData(value=True)

            executable = and_fn

        elif isinstance(function, Or):

            def or_fn(arguments: tuple[Data, ...]) -> Data:
                for data in arguments:
                    if cast(BoolData, data).value:
                        return BoolData(value=True)
                return BoolData(value=False)

            executable = or_fn

        elif isinstance(function, LiteralInt):

            def literal_int(arguments: tuple[Data, ...]) -> Data:
                return IntData(value=function.value)

            executable = literal_int

        elif isinstance(function, LiteralFloat):

            def literal_float(arguments: tuple[Data, ...]) -> Data:
                return FloatData(value=function.value)

            executable = literal_float

        elif isinstance(function, LiteralString):

            def literal_string(arguments: tuple[Data, ...]) -> Data:
                return StringData(value=function.value)

            executable = literal_string

        elif isinstance(function, LiteralBool):

            def literal_bool(arguments: tuple[Data, ...]) -> Data:
                return BoolData(value=function.value)

            executable = literal_bool

        elif isinstance(function, ProjectToSpan):

            def project_to_span(arguments: tuple[Data, ...]) -> Data:
                data = cast(LabelRefData, arguments[0])
                return TextSpanData(
                    value=TextSpan(
                        start=data.value.start,
                        end=data.value.end,
                        chapter_content_id=data.value.chapter_content_id,
                    )
                )

            executable = project_to_span

        elif isinstance(function, Rename):
            rename_function = function

            def rename(arguments: tuple[Data, ...]) -> Data:
                data = cast(DataObj, arguments[0])
                fields = dict(data.fields)
                renamed = {pair.new_name: fields.pop(pair.old_name) for pair in rename_function.rename_pairs}
                fields.update(renamed)
                return DataObj(fields=fields)

            executable = rename

        elif isinstance(function, Construct):
            compiled_fields = {
                field_name: self.compile(field_function) for field_name, field_function in function.fields.items()
            }

            def construct(arguments: tuple[Data, ...]) -> Data:
                return DataObj(
                    fields={
                        field_name: cast(
                            DataType,
                            _evaluate_in_environment(field_function, arguments),
                        )
                        for field_name, field_function in compiled_fields.items()
                    }
                )

            executable = construct

        elif isinstance(function, Extend):
            compiled_fields = {
                field_name: self.compile(field_function) for field_name, field_function in function.fields.items()
            }

            def extend(arguments: tuple[Data, ...]) -> Data:
                data = cast(DataObj, arguments[0])
                fields = dict(data.fields)
                fields.update(
                    {
                        field_name: cast(
                            DataType,
                            _evaluate_in_environment(field_function, arguments),
                        )
                        for field_name, field_function in compiled_fields.items()
                    }
                )
                return DataObj(fields=fields)

            executable = extend

        elif isinstance(function, Call):
            compiled_arguments = tuple(self.compile(argument) for argument in function.arguments)
            compiled_function = self.compile(function.function)

            def call(arguments: tuple[Data, ...]) -> Data:
                call_arguments = tuple(_evaluate_in_environment(argument, arguments) for argument in compiled_arguments)
                return compiled_function(call_arguments)

            executable = call

        else:
            assert_never(function)

        return CompiledPythonFunction(signature=function.signature, executable=executable)
