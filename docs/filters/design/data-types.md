# Future filter type-system extensions

**Last updated:** 2026-07-28

> **Status:** Future design. These are possible extensions to the implemented
> flat type system. See [../data-types.md](../data-types.md) for current
> behavior.

The current type system deliberately supports a small first version: one flat
record of tagged scalar or reference values. The capabilities below should be
introduced only when a concrete workflow requires them.

## Recursive records

Nested records would let one instance preserve meaningful structure:

```text
Record {
    label: LabelRef
    context: Record {
        text: String
        target: TextSpan
    }
    review: Record {
        comment: Mutable<String>
    }
}
```

Adding recursion requires limits on nesting depth and total nodes, recursive
schema compatibility, nested data validation, and a stable serialized form.
The current `Get` operation and dependency resolver would also need general
key-path traversal.

## Semantic context types

The current `textOf` and `textAround` functions return ordinary strings.
Purpose-built types could preserve the relationship between surrounding text
and its target span:

- `SentenceContext`
- `ParagraphContext`
- `ChapterContext`

Semantic context types would allow the frontend to highlight the target and
would prevent ordinary strings from being mistaken for source-backed context.
Their exact serialized representation remains open.

## Versioned type and function registries

Current type tags and function node names are defined directly by backend code.
A durable public workflow format may eventually need stable identifiers and
versions for:

- elementary and semantic types;
- built-in function behavior;
- serialized function definitions;
- frontend renderers and editors.

Removing or changing a registered definition must not silently change the
meaning of persisted workflows. The versioning policy should be designed
alongside a migration or compatibility strategy rather than added only as a
field.

## Editable values and key paths

Scalar schema fields carry a `mutable` capability. The annotation runner adds
new mutable scalar fields with defaults, and the instance update API accepts
partial scalar field patches. It:

1. Resolves each top-level field against the workflow schema.
2. Confirms that the field is mutable.
3. Validates the replacement value with strict type semantics.
4. Atomically merges the validated fields without replacing other values.

Authorship and revision metadata are not currently recorded.

`TextSpan`, `LabelRef`, and other NovelTL resource references must remain
immutable.

## Optional fields and collections

The current schema requires an exact set of top-level fields for persisted
instances. Optional fields, arrays, maps, unions, and multi-output functions
should not be added speculatively. Each would affect compatibility, persistence
queries, generic rendering, and function signatures.

## Frontend rendering

A future workflow UI may use generic schema-driven rendering for scalar values
and focused renderers for semantic references and contexts. It should compose
the project's existing shadcn components and semantic theme tokens rather than
introducing a separate filter-specific component system.

## Open questions

- Which implemented workflow first requires nested records?
- Do type and function versions form immutable registrations or deployment
  compatibility ranges?
- Should editable values retain authorship and revision history from the first
  annotation implementation?
- Which semantic types need custom persistence or frontend renderers?
- What limits should bound recursive schemas and function ASTs?
