# Filter data types

> **Status:** Design document. This describes the target type system and
> includes capabilities that are not implemented yet. See
> [README.md](README.md) for the current implementation boundary.

## Motivation

The filter system needs to operate on more than one fixed shape of data.
Some filters begin with labels, while others may begin with an unlabeled text
range, a word, a group of related occurrences, or a value produced by an
earlier operation. The useful information may also be nested. For example, a
review candidate might contain a label, a sentence around that label, a
normalized word, and a reviewer comment.

The current filter interface couples candidate discovery, context retrieval,
decision-making, and application inside one filter implementation. This makes
it difficult to reuse basic behavior:

- Sentence extraction should work for any value that can identify a text
  range, not only for labels produced by a particular filter.
- String operations such as normalization and comparison should be usable in
  many workflows.
- Application behavior should depend on the data being applied, such as a
  label reference or text span, rather than on the filter that originally
  discovered it.
- Users and future AI clients should be able to compose safe, predefined
  operations without submitting executable code.
- Some workflow-local values, such as comments or manual classifications,
  should be editable, while references to NovelTL data must remain immutable.

To support these requirements, workflows need a small persistent type system.
The type system describes the shape and meaning of every instance in a
workflow, determines which operations are compatible with it, and provides
enough information for the frontend to render and edit permitted values.

## Schemas and instances

A workflow has one **instance schema** and a collection of **instances** that
conform to that schema.

Schemas are recursive records. Each record maps string keys to either another
record schema or an elementary type. Conceptually:

```text
Record {
    label: LabelRef
    normalizedWord: String
    context: Record {
        sentence: String
        target: TextSpan
    }
    review: Record {
        comment: Mutable<String>
    }
}
```

The persisted representation should be a constrained schema abstract syntax
tree rather than arbitrary application code. It may be encoded as JSON and
translated to JSON Schema for validation and form rendering, but NovelTL does
not need to support every feature of JSON Schema.

Every instance must be validated against the workflow schema when it is
created, loaded, or changed. A schema is part of the persisted workflow
contract; it must not be inferred independently by each client.

## Elementary types

Elementary types are registered semantic leaf types. The initial registry is
expected to include ordinary scalar values such as:

- `String`
- `Integer`
- `Float`
- `Boolean`
- `TextSpan`
- `LabelRef`

Additional types should be introduced in response to concrete workflows rather
than added speculatively. Each registered type needs:

- A stable name and version.
- A serialized representation.
- Runtime validation.
- Frontend display behavior, or a generic fallback.
- A declaration of whether it may be wrapped in `Mutable<T>`.

### `TextSpan`

A `TextSpan` is an immutable reference to a range of a specific chapter-content
version. It contains enough information to resolve the referenced text and to
detect when that reference has become stale. At minimum, its semantics include:

- The immutable chapter-content identity.
- Start and end offsets within that content.

A `TextSpan` does not silently move to a newer content version. If the chapter
is edited, the old span remains a reference to the old version and may no
longer be applicable.

### `LabelRef`

A `LabelRef` is an immutable reference to a concrete label and the versioned
chapter content to which it belongs. It contains or can resolve the label's
word, range, category, score, dirty state, and other label metadata.

A `LabelRef` can be projected to a `TextSpan`. Context operations therefore do
not need separate implementations for every kind of value that happens to
contain a label.

Like `TextSpan`, a `LabelRef` never silently follows a label through a chapter
edit or label-data replacement. Staleness must be detected explicitly.

### Context types

Context is represented by a small set of predetermined semantic types, such as:

- `SentenceContext`
- `ParagraphContext`
- `ChapterContext`

Context getters accept canonical input types such as `TextSpan` and return one
of these context structures. The returned context retains its relationship to
the source span so a reviewer or renderer can identify the target inside the
surrounding text.

Keeping context getters focused on canonical types prevents every filter from
reimplementing sentence, paragraph, and chapter extraction.

## Mutability

Mutability is part of the workflow schema, not a property inferred from the
serialized value. `Mutable<T>` marks a workflow-local value that the user or an
authorized client may edit.

For example:

```text
Mutable<String>
Mutable<Integer>
```

Only types explicitly branded as capable of mutation may be wrapped.
`TextSpan`, `LabelRef`, and other references to NovelTL domain data are always
immutable and must reject mutable wrapping.

The backend must enforce this rule both statically and at runtime:

- Developer-authored schema descriptors can use a marker base type or bounded
  generic so type checking rejects invalid combinations.
- Persisted schemas must be checked against registry metadata when decoded,
  because Python generic bounds do not enforce data loaded from a database.
- Update endpoints must resolve the requested key path and verify that its
  terminal schema is mutable before accepting a change.

The underlying value of `Mutable<String>` may still be serialized as a normal
string. The schema is what grants permission to replace it.

## Key paths

Nested fields are addressed by **key paths**, represented as arrays of keys:

```text
["context", "sentence"]
["review", "comment"]
["label"]
```

Key paths are resolved against the schema before they are resolved against an
instance. An invalid path, incompatible source type, or immutable destination
must fail validation before an operation begins.

The first version only needs record-key access. Array indexing, wildcards, and
other traversal features should be added only when a concrete workflow
requires them.

## Registered operations

Workflow operations refer to registered, versioned functions. Persisted
workflows must never contain arbitrary Python, JavaScript, SQL, or other
executable code supplied by a user.

Each registered function declares:

- A stable name and version.
- Its input type or named input bindings.
- Its parameter schema.
- Its output type.
- Whether it is pure or requires external data.
- Whether it is deterministic.
- Its authorization requirements, if any.

Examples of elementary functions include:

```text
toUpper: String -> String
trim: String -> String
equalsString(expected: String): String -> Boolean
containsString(fragment: String): String -> Boolean
lessThan(threshold: Float): Float -> Boolean
sentenceContext: TextSpan -> SentenceContext
```

External-data operations, such as resolving sentence context, are still
registered functions. Their declaration makes their effects and compatibility
visible even though they cannot be evaluated as pure scalar functions.

### Field mappings

A field mapping derives a value from one or more source paths and writes it to
a destination path. A mapping conceptually contains:

```text
input bindings + registered function + parameters + destination path
```

Named input bindings allow an operation to consume more than one field without
making the ordering of path arrays meaningful.

Before execution, the workflow engine validates that:

- Every source path exists.
- Source types match the function's input declaration.
- Parameters match the function's parameter schema.
- The destination is legal and does not conflict with another destination in
  the same operation.
- The resulting workflow schema is valid.

### Predicates

Instance predicates are recursively composable:

```text
Predicate =
    At(keyPath, predicateFunction, parameters)
    | And(Predicate...)
    | Or(Predicate...)
    | Not(Predicate)
```

Every predicate function accepts the type found at its key path and returns a
boolean. Filtering an instance collection uses this expression without
embedding filter-specific code in the workflow.

## Type compatibility

Operations are available only when their required inputs can be satisfied by
the current instance schema. Compatibility must be checked on the backend even
when the frontend has already hidden incompatible operations.

The type system should prefer explicit projections over implicit conversions.
For example, a sentence-context getter accepts `TextSpan`; using it with a
`LabelRef` first applies the registered `LabelRef -> TextSpan` projection.
This makes persisted operations reproducible and avoids surprising behavior
when types evolve.

## Persistence and versioning requirements

- Workflow schemas, elementary types, and registered functions must use stable
  identifiers and versions.
- Removing or changing a registered type or function must not silently change
  the meaning of an existing workflow.
- Instances should be stored as independently addressable records rather than
  one large JSON array on the workflow row. This is required for pagination,
  sampling, partial failures, and large novels.
- The schema is stored once per compatible workflow collection or materialized
  stage; instances store their validated payloads.
- References to NovelTL data retain immutable source identities so application
  can perform mandatory staleness checks.

## Open questions

- The exact persisted schema encoding and its supported JSON Schema subset.
- The initial catalog of elementary types and functions.
- Whether function versions are immutable registrations or separate deployment
  versions with compatibility guarantees.
- How multi-output functions and optional fields should be represented.
- Whether mutable values need authorship and revision metadata in the first
  implementation.
