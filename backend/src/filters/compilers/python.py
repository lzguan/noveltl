from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, assert_never

from src.filters.data_types import (
    BoolData,
    Data,
    DataObj,
    DataType,
    FloatData,
    IntData,
    LabelRefData,
    Schema,
    StringData,
    TextSpan,
    TextSpanData,
    validate,
    validate_compatible,
)
from src.filters.functions import (
    And,
    Call,
    Compare,
    Construct,
    Custom,
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
        if len(arguments) != len(self.signature.args):
            raise ValueError(f"Function requires {len(self.signature.args)} arguments; received {len(arguments)}.")

        for index, (argument, parameter) in enumerate(zip(arguments, self.signature.args, strict=True)):
            if isinstance(parameter, Schema):
                if not isinstance(argument, DataObj):
                    raise ValueError(f"Invalid argument {index}: expected an object value.")
                try:
                    validate_compatible(argument, parameter)
                except ValueError as exc:
                    raise ValueError(f"Invalid argument {index}: {exc}") from exc
            elif isinstance(argument, DataObj) or argument.type != parameter.type:
                actual_type = "object" if isinstance(argument, DataObj) else argument.type
                raise ValueError(
                    f"Invalid argument {index}: expected type '{parameter.type}', received '{actual_type}'."
                )

        result = self.executable(arguments)
        output = self.signature.output
        if isinstance(output, Schema):
            if not isinstance(result, DataObj):
                raise ValueError("Function returned an invalid value: expected an object value.")
            try:
                validate(result, output)
            except ValueError as exc:
                raise ValueError(f"Function returned an invalid value: {exc}") from exc
        elif isinstance(result, DataObj) or result.type != output.type:
            actual_type = "object" if isinstance(result, DataObj) else result.type
            raise ValueError(
                f"Function returned an invalid value: expected type '{output.type}', received '{actual_type}'."
            )

        return result

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


def _require_object(data: Data, function_name: str) -> DataObj:
    if not isinstance(data, DataObj):
        raise ValueError(f"The '{function_name}' function can only be applied to objects.")
    return data


def _require_elementary(data: Data, function_name: str) -> DataType:
    if isinstance(data, DataObj):
        raise ValueError(f"The '{function_name}' function must produce an elementary value.")
    return data


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
                data = _require_object(arguments[0], function.name)
                return data.fields[function.field_name]

            executable = get

        elif isinstance(function, Compare):

            def compare(arguments: tuple[Data, ...]) -> Data:
                left, right = arguments
                if isinstance(left, DataObj) or isinstance(right, DataObj):
                    raise ValueError("The 'compare' function requires elementary values.")
                return BoolData(value=_compare_values(left.value, right.value, function.op))

            executable = compare

        elif isinstance(function, Not):

            def not_fn(arguments: tuple[Data, ...]) -> Data:
                data = arguments[0]
                if not isinstance(data, BoolData):
                    raise ValueError("The 'not' function can only be applied to boolean data.")
                return BoolData(value=not data.value)

            executable = not_fn

        elif isinstance(function, And):

            def and_fn(arguments: tuple[Data, ...]) -> Data:
                for data in arguments:
                    if not isinstance(data, BoolData):
                        raise ValueError("The 'and' function can only be applied to boolean data.")
                    if not data.value:
                        return BoolData(value=False)
                return BoolData(value=True)

            executable = and_fn

        elif isinstance(function, Or):

            def or_fn(arguments: tuple[Data, ...]) -> Data:
                for data in arguments:
                    if not isinstance(data, BoolData):
                        raise ValueError("The 'or' function can only be applied to boolean data.")
                    if data.value:
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
                data = arguments[0]
                if not isinstance(data, LabelRefData):
                    raise ValueError("The 'projectToSpan' function can only be applied to label reference data.")
                return TextSpanData(
                    value=TextSpan(
                        start=data.value.start,
                        end=data.value.end,
                        chapter_content_id=data.value.chapter_content_id,
                    )
                )

            executable = project_to_span

        elif isinstance(function, Rename):

            def rename(arguments: tuple[Data, ...]) -> Data:
                data = _require_object(arguments[0], function.name)
                fields = dict(data.fields)
                renamed = {pair.new_name: fields.pop(pair.old_name) for pair in function.rename_pairs}
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
                        field_name: _require_elementary(
                            _evaluate_in_environment(field_function, arguments),
                            function.name,
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
                data = _require_object(arguments[0], function.name)
                fields = dict(data.fields)
                fields.update(
                    {
                        field_name: _require_elementary(
                            _evaluate_in_environment(field_function, arguments),
                            function.name,
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
                call_arguments = tuple(
                    _evaluate_in_environment(argument, arguments) for argument in compiled_arguments
                )
                return compiled_function(call_arguments)

            executable = call

        elif isinstance(function, Custom):
            compiled_root = self.compile(function.root)

            def custom(arguments: tuple[Data, ...]) -> Data:
                return compiled_root(arguments)

            executable = custom

        else:
            assert_never(function)

        return CompiledPythonFunction(signature=function.signature, executable=executable)
