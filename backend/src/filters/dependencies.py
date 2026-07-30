"""
Dependency resolution for semantic functions.

A dependency is a resource that a function requires to execute. We represent a
function dependency as a resource name, an argument index, and a key path. The
argument index identifies which root function argument the dependency is
derived from, and the key path identifies which field of that argument the
dependency is derived from.

The dependencies of a function are resolved by symbolically evaluating the
function AST.

The algorithm is approximately:
1. For each root argument, create a symbolic value that represents the
   argument's structure and tracks the origin of each field.
2. Do a "virtual" evaluation of the function, propagating the symbolic values
   through the function's operations. When a resource dependency is
   encountered, record the origin of the value that produced it.
3. Return the set of resolved dependencies, which are the resource names and
   their corresponding argument indices and key paths.
"""

from dataclasses import dataclass

from src.filters.data_types import FieldName, Schema, SchemaField
from src.filters.functions import (
    And,
    Call,
    Compare,
    Construct,
    EndOf,
    Extend,
    Function,
    FunctionType,
    Get,
    LengthOf,
    LiteralBool,
    LiteralFloat,
    LiteralInt,
    LiteralString,
    Not,
    Or,
    ProjectToSpan,
    Rename,
    ResourceDependency,
    ResourceName,
    ScoreOf,
    StartOf,
    TextAround,
    TextOf,
    WordOf,
)


@dataclass(frozen=True, order=True, slots=True)
class ResolvedResourceDependency:
    """A batch-load requirement bound to a root function argument."""

    resource: ResourceName
    argument_index: int
    key_path: tuple[FieldName, ...]


@dataclass(frozen=True, slots=True)
class SourceOrigin:
    """The root argument and field path from which a symbolic value originated."""

    argument_index: int
    key_path: tuple[FieldName, ...]


@dataclass(frozen=True, slots=True)
class SymbolicScalar:
    """
    Symbolic value that represents a scalar value and tracks its origin.
    """

    origins: frozenset[SourceOrigin]


@dataclass(slots=True)
class SymbolicObject:
    """
    Symbolic value that represents an object value and tracks its origin.
    """

    fields: dict[FieldName, SymbolicScalar]


type SymbolicValue = SymbolicScalar | SymbolicObject


def resolve_dependencies(function: FunctionType) -> tuple[ResolvedResourceDependency, ...]:
    """
    Resolve intrinsic function dependencies to root argument key paths.

    Resolution symbolically evaluates the function AST. Values derived from a
    root argument retain their source origin through structural operations such
    as Get, Rename, Construct, Extend, Call, and ProjectToSpan. A resource
    dependency must ultimately resolve to at least one root argument origin.
    """

    requirements: set[ResolvedResourceDependency] = set()
    arguments = tuple(
        symbolic_argument(argument_schema, argument_index)
        for argument_index, argument_schema in enumerate(function.signature.args)
    )
    evaluate(function, arguments, requirements)
    return tuple(sorted(requirements))


def symbolic_argument(schema: Schema | SchemaField, argument_index: int) -> SymbolicValue:
    if isinstance(schema, Schema):
        return SymbolicObject(
            fields={
                field_name: SymbolicScalar(origins=frozenset({SourceOrigin(argument_index, (field_name,))}))
                for field_name in schema.fields
            }
        )
    return SymbolicScalar(origins=frozenset({SourceOrigin(argument_index, ())}))


def evaluate(
    function: Function,
    arguments: tuple[SymbolicValue, ...],
    requirements: set[ResolvedResourceDependency],
) -> SymbolicValue:
    _resolve_intrinsic_dependencies(function, arguments, requirements)

    if isinstance(function, LiteralString | LiteralInt | LiteralFloat | LiteralBool):
        return SymbolicScalar(origins=frozenset())

    if isinstance(function, Get):
        data = _require_object(arguments[0], function)
        try:
            return data.fields[function.field_name]
        except KeyError as exc:
            raise ValueError(f"Function '{function.name}' references unknown field '{function.field_name}'.") from exc

    if isinstance(function, ProjectToSpan):
        return _require_scalar(arguments[0], function)

    if isinstance(function, Rename):
        data = _require_object(arguments[0], function)
        fields = dict(data.fields)
        renamed = {pair.new_name: fields.pop(pair.old_name) for pair in function.rename_pairs}
        fields.update(renamed)
        return SymbolicObject(fields=fields)

    if isinstance(function, Construct):
        return SymbolicObject(
            fields={
                field_name: _require_scalar(
                    _evaluate_in_environment(field_function, arguments, requirements),
                    field_function,
                )
                for field_name, field_function in function.fields.items()
            }
        )

    if isinstance(function, Extend):
        data = _require_object(arguments[0], function)
        fields = dict(data.fields)
        fields.update(
            {
                field_name: _require_scalar(
                    _evaluate_in_environment(field_function, arguments, requirements),
                    field_function,
                )
                for field_name, field_function in function.fields.items()
            }
        )
        return SymbolicObject(fields=fields)

    if isinstance(function, Call):
        call_arguments = tuple(
            _evaluate_in_environment(argument, arguments, requirements) for argument in function.arguments
        )
        return evaluate(function.function, call_arguments, requirements)

    if isinstance(
        function,
        Compare | And | Or | Not | StartOf | EndOf | LengthOf | TextOf | TextAround | WordOf | ScoreOf,
    ):
        return SymbolicScalar(origins=frozenset())

    raise TypeError(f"Unsupported function type during dependency resolution: {type(function).__name__}")


def _evaluate_in_environment(
    function: Function,
    environment: tuple[SymbolicValue, ...],
    requirements: set[ResolvedResourceDependency],
) -> SymbolicValue:
    if len(function.signature.args) == 0:
        return evaluate(function, (), requirements)
    return evaluate(function, environment, requirements)


def _resolve_intrinsic_dependencies(
    function: Function,
    arguments: tuple[SymbolicValue, ...],
    requirements: set[ResolvedResourceDependency],
) -> None:
    for dependency in function.dependencies:
        if not isinstance(dependency, ResourceDependency):
            raise TypeError(f"Unsupported dependency type: {dependency.dependency_type}")
        if dependency.argument_index >= len(arguments):
            raise ValueError(
                f"Function '{function.name}' dependency references argument "
                f"{dependency.argument_index}, but only {len(arguments)} arguments are available."
            )

        value = _require_scalar(arguments[dependency.argument_index], function)
        if not value.origins:
            raise ValueError(
                f"Function '{function.name}' resource dependency cannot be resolved to a root argument key path."
            )
        requirements.update(
            ResolvedResourceDependency(
                resource=dependency.resource,
                argument_index=origin.argument_index,
                key_path=origin.key_path,
            )
            for origin in value.origins
        )


def _require_scalar(value: SymbolicValue, function: Function) -> SymbolicScalar:
    if not isinstance(value, SymbolicScalar):
        raise ValueError(f"Function '{function.name}' requires an elementary argument.")
    return value


def _require_object(value: SymbolicValue, function: Function) -> SymbolicObject:
    if not isinstance(value, SymbolicObject):
        raise ValueError(f"Function '{function.name}' requires an object argument.")
    return value
