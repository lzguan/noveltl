# Filter data types

**Last updated:** 2026-08-05

The filter subsystem uses a small tagged type system for persisted workflow
schemas, instance values, and function signatures. It validates data loaded
from JSON without relying on Python runtime types or arbitrary JSON Schema
features.

The current schema model is flat: a workflow instance is one record whose
fields are elementary scalar or reference values. Nested records, optional
fields, and collections are not implemented.

## Schemas

A `Schema` contains a map of field names to schema fields:

```json
{
  "kind": "schema",
  "fields": {
    "label": {
      "kind": "field",
      "type": "labelRef",
      "mutable": false
    },
    "comment": {
      "kind": "field",
      "type": "string",
      "mutable": true
    }
  }
}
```

The `kind` discriminator separates record schemas from elementary fields. Field
names must be non-empty, contain a non-whitespace character, and be at most 128
characters. A schema may contain at most 256 fields.

Schemas and schema fields are frozen Pydantic models. Unknown properties are
rejected.

## Elementary types

The implemented elementary type tags are:

| Type | Stored value | Mutable |
| --- | --- | --- |
| `string` | Strict JSON string | Optional |
| `int` | Strict JSON integer | Optional |
| `float` | Finite JSON number | Optional |
| `bool` | Strict JSON boolean | Optional |
| `textSpan` | Immutable chapter-content range | No |
| `labelRef` | Immutable label and chapter-content reference | No |

Strict parsing prevents values such as `"12"` or `true` from being accepted as
integers. Floats reject NaN and infinity because they do not have portable
JSON, SQL, or comparison semantics.

### Text spans

A `TextSpan` contains:

- `chapterId`;
- `chapterContentId`;
- a non-negative inclusive `start`;
- a non-negative exclusive `end`.

The model requires `end >= start`, so an empty span is valid. It does not check
the referenced text's existence or length during JSON parsing. Functions that
read the text resolve the immutable chapter-content ID through an execution
context.

### Label references

A `LabelRef` contains:

- `chapterId`;
- `chapterContentId`;
- `labelId`;
- `labelDataId`;
- `labelGroupId`.

The reference captures the label and chapter-content identities, but it does
not snapshot the label's range, word, score, category, or dirty state. The
implemented `wordOf`, `scoreOf`, and `projectToSpan` functions load the current
label row by `labelId` when a runner executes. `projectToSpan` combines that
row's current offsets with the reference's stored chapter IDs.

Reference integrity, authorization, and staleness validation are not part of
the Pydantic value model and do not yet have a separate execution preflight.

## Instance values

An instance is stored as a tagged `DataObj`. Every field contains a tagged
elementary value:

```json
{
  "obj": true,
  "fields": {
    "term": {
      "obj": false,
      "type": "string",
      "value": "青石城"
    }
  }
}
```

`Schema` and `DataObj` have the same flat field shape, but mutability belongs
only to the schema. A mutable string and an immutable string have the same
stored data representation.

## Validation

There are two validation modes:

- `validate(data, schema)` requires identical field names and matching
  elementary type tags. It is intended for exact persisted-instance
  conformance.
- `validate_compatible(data, schema)` requires the declared fields and types
  but permits extra fields. It is useful when a function reads only part of an
  instance.

Pydantic parsing validates each tagged value before either helper runs.
Current runners parse stored values and validate their function/schema
contracts, but they do not consistently call exact instance validation for
every loaded row.

## Structural compatibility

`extends(extension, base)` answers whether one schema or field can be used
where another is required.

Record schemas are structurally compatible: the extension must provide every
field required by the base, but may contain additional fields. Elementary
types must have the same type tag.

Mutability behaves as a capability:

- a mutable field may satisfy a read-only requirement;
- a mutable field may satisfy a mutable requirement;
- an immutable field may satisfy a read-only requirement;
- an immutable field cannot satisfy a mutable requirement.

This rule lets ordinary functions read mutable review data without granting
them permission to update it.

## Persistence

Workflow schemas and instance values are stored as PostgreSQL JSONB in the
filter persistence models. Each instance is an independently addressable row,
which allows batch processing without loading an entire workflow into memory.

The current format has no explicit schema or type version. Persisted function
definitions likewise rely on the backend's current tagged models. Versioning
and compatibility policy remain future design work.

## Code guide

- [`data_types.py`](../../backend/src/filters/data_types.py): models,
  discriminated unions, validation, and compatibility
- [`test_data_types.py`](../../backend/tests/filters/test_data_types.py):
  serialization and validation examples
- [functions.md](functions.md): how these types form function signatures
- [Future type-system extensions](design/data-types.md): deliberately deferred
  capabilities
