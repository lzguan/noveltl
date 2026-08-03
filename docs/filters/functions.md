# Filter functions

**Last updated:** 2026-07-30

Filter functions are persisted descriptions of safe computations. They form a
closed, discriminated abstract syntax tree (AST): each node has a `name` tag,
validated configuration, a computed signature, and optional external resource
dependencies.

The AST contains no user-supplied source code. The Python compiler translates
validated nodes into in-memory callables.

## Signatures

Every function computes a `Signature` containing:

- zero or more argument schemas;
- one output schema.

An argument or output may be an elementary field or a flat record schema.
Signatures are computed fields and cannot be supplied or overridden in
persisted JSON.

Primitive functions such as `compare` may accept multiple arguments.
Expressions used directly inside `construct` or `extend` must be nullary or
unary against their shared input record. The `call` node binds a
multiple-argument function to expressions evaluated against that record.

## Function catalog

### Values and field access

| Node | Behavior |
| --- | --- |
| `literalString` | Produce a string literal |
| `literalInt` | Produce an integer literal |
| `literalFloat` | Produce a finite float literal |
| `literalBool` | Produce a boolean literal |
| `get` | Read one named field from an input record |

Literals are immutable by default but may declare a mutable scalar output.
`get` declares the field type and mutability it requires, allowing its
signature to participate in structural compatibility checks.

### Scalar and logical operations

| Node | Behavior |
| --- | --- |
| `compare` | Compare two strings, integers, floats, or booleans |
| `add` | Add one or more integers or floats |
| `subtract` | Subtract two integers or two floats |
| `max` | Return the largest of one or more integers or floats |
| `min` | Return the smallest of one or more integers or floats |
| `concat` | Concatenate one or more strings in argument order |
| `contains` | Test whether the second string occurs verbatim in the first |
| `float` | Convert an integer to a float |
| `floor` | Round a float down to an integer |
| `ceil` | Round a float up to an integer |
| `round` | Round a float to the nearest integer, with ties to even |
| `and` | Require all boolean arguments to be true |
| `or` | Require at least one boolean argument to be true |
| `not` | Negate one boolean |

Comparisons support `eq`, `ne`, `lt`, `le`, `gt`, and `ge`. Boolean values
support only equality and inequality. `and` and `or` require at least one
argument. `add`, `max`, `min`, and `concat` declare their arity with `num`, from
one through 256 arguments. Numeric operations declare either `int` or `float`
and do not perform implicit promotion. Float addition evaluates left-to-right.
`contains` is case-sensitive and treats an empty needle as a match.

### References and text

| Node | Behavior | External resource |
| --- | --- | --- |
| `projectToSpan` | Resolve current offsets and return a text span | Label row |
| `wordOf` | Read a label's current word | Label row |
| `scoreOf` | Read a label's current score | Label row |
| `startOf` | Return a span's start offset | None |
| `endOf` | Return a span's end offset | None |
| `lengthOf` | Return `end - start` | None |
| `textOf` | Return the referenced text slice | Chapter content |
| `textAround` | Return the slice plus configured character slack | Chapter content |

`textAround` returns an ordinary string; sentence, paragraph, and chapter
context types are not implemented.

### Record composition

| Node | Behavior |
| --- | --- |
| `construct` | Build a new record from named elementary-output expressions |
| `extend` | Preserve an input record and add derived fields |
| `if` | Lazily select one of two expressions and project it to a declared output schema |
| `rename` | Rename one or more fields simultaneously |
| `call` | Bind a function's arguments to expressions over one input record |

`construct` and `extend` require at least one derived field and reject object
outputs for individual fields. `extend` rejects collisions with existing
fields. `rename` rejects missing sources, duplicate sources or destinations,
and collisions with fields that are not being renamed. `if` validates and
compiles both branches, evaluates only the selected branch, and conservatively
collects dependencies from both.

## Composition example

The implemented pipeline tests build a low-score predicate by composing
existing nodes:

```python
score = Call(
    input_schema=LABEL_SOURCE_SCHEMA,
    function=ScoreOf(),
    arguments=(Get(field_name="label", type="labelRef"),),
)

bad_score = Call(
    input_schema=LABEL_SOURCE_SCHEMA,
    function=Compare(type="float", op="lt"),
    arguments=(score, LiteralFloat(value=0.6)),
)
```

The outer `call` has one record argument and returns a boolean. A filter runner
can therefore verify that the source workflow structurally satisfies the
predicate before compiling it.

## External dependencies

Some functions need NovelTL data that is not embedded in the instance.
`wordOf` and `scoreOf` declare a label dependency; `textOf` and `textAround`
declare a chapter-content dependency.

The dependency resolver symbolically evaluates the AST and traces each
dependency back to a root argument and field path. It understands field access,
projection, calls, record construction, extension, and renaming. Duplicate
requirements are removed and the result is ordered deterministically.

Before executing a batch, a runner collects all referenced IDs and asks the
Python execution context to load them in bulk. The compiled function then reads
from the context's per-batch caches instead of issuing one query per instance.

The current context loads label words and scores and complete chapter-content
text. It does not enforce user permissions; runners currently operate as
trusted backend code.

## Compilation

`PythonCompiler.compile()` recursively compiles a validated AST into a
`CompiledPythonFunction`. The compiled object retains the original computed
signature and accepts:

1. a tuple of tagged data arguments;
2. a `PythonExecutionContext`.

The compiler relies on prior model and runner validation for type safety. Its
internal casts do not perform a second dynamic signature check for every call.

## Persistence

`FunctionDefinition` stores:

- a generated ID;
- a namespace;
- a function name unique within that namespace;
- the serialized function AST as JSONB.

The current model does not store a function version, ownership, authorization
requirements, purity, determinism, or deployment compatibility metadata.

## Limits

Current parse-time limits include:

- 256 function arguments;
- 256 schema or constructed fields;
- 128 simultaneous rename pairs;
- 10,000 characters in a string literal.

There is not yet a semantic limit on total AST nodes or nesting depth.

## Code guide

- [`functions.py`](../../backend/src/filters/functions.py): AST nodes and
  signatures
- [`dependencies.py`](../../backend/src/filters/dependencies.py): symbolic
  dependency resolution
- [`compilers/python.py`](../../backend/src/filters/compilers/python.py):
  compiler implementation
- [`context/python.py`](../../backend/src/filters/context/python.py): resource
  loading and caches
- [`test_functions.py`](../../backend/tests/filters/test_functions.py) and
  [`test_python_compiler.py`](../../backend/tests/filters/test_python_compiler.py):
  composition examples
