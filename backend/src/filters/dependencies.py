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
    """A semantic resource dependency bound to a root function argument."""

    resource: ResourceName
    argument_index: int
    key_path: tuple[FieldName, ...]


@dataclass(frozen=True, slots=True)
class _SourceOrigin:
    argument_index: int
    key_path: tuple[FieldName, ...]


@dataclass(frozen=True, slots=True)
class _SymbolicScalar:
    origins: frozenset[_SourceOrigin]


@dataclass(slots=True)
class _SymbolicObject:
    fields: dict[FieldName, _SymbolicScalar]


type _SymbolicValue = _SymbolicScalar | _SymbolicObject


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
        _symbolic_argument(argument_schema, argument_index)
        for argument_index, argument_schema in enumerate(function.signature.args)
    )
    _evaluate(function, arguments, requirements)
    return tuple(sorted(requirements))


def _symbolic_argument(schema: Schema | SchemaField, argument_index: int) -> _SymbolicValue:
    if isinstance(schema, Schema):
        return _SymbolicObject(
            fields={
                field_name: _SymbolicScalar(origins=frozenset({_SourceOrigin(argument_index, (field_name,))}))
                for field_name in schema.fields
            }
        )
    return _SymbolicScalar(origins=frozenset({_SourceOrigin(argument_index, ())}))


def _evaluate(
    function: Function,
    arguments: tuple[_SymbolicValue, ...],
    requirements: set[ResolvedResourceDependency],
) -> _SymbolicValue:
    _resolve_intrinsic_dependencies(function, arguments, requirements)

    if isinstance(function, LiteralString | LiteralInt | LiteralFloat | LiteralBool):
        return _SymbolicScalar(origins=frozenset())

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
        return _SymbolicObject(fields=fields)

    if isinstance(function, Construct):
        return _SymbolicObject(
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
        return _SymbolicObject(fields=fields)

    if isinstance(function, Call):
        call_arguments = tuple(
            _evaluate_in_environment(argument, arguments, requirements) for argument in function.arguments
        )
        return _evaluate(function.function, call_arguments, requirements)

    if isinstance(
        function,
        Compare | And | Or | Not | StartOf | EndOf | LengthOf | TextOf | TextAround | WordOf | ScoreOf,
    ):
        return _SymbolicScalar(origins=frozenset())

    raise TypeError(f"Unsupported function type during dependency resolution: {type(function).__name__}")


def _evaluate_in_environment(
    function: Function,
    environment: tuple[_SymbolicValue, ...],
    requirements: set[ResolvedResourceDependency],
) -> _SymbolicValue:
    if len(function.signature.args) == 0:
        return _evaluate(function, (), requirements)
    return _evaluate(function, environment, requirements)


def _resolve_intrinsic_dependencies(
    function: Function,
    arguments: tuple[_SymbolicValue, ...],
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


def _require_scalar(value: _SymbolicValue, function: Function) -> _SymbolicScalar:
    if not isinstance(value, _SymbolicScalar):
        raise ValueError(f"Function '{function.name}' requires an elementary argument.")
    return value


def _require_object(value: _SymbolicValue, function: Function) -> _SymbolicObject:
    if not isinstance(value, _SymbolicObject):
        raise ValueError(f"Function '{function.name}' requires an object argument.")
    return value
