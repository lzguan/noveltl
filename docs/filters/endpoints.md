# Filter API endpoints

> **Status:** Draft. This document defines the intended public HTTP API. The
> filter subsystem is not yet exposed through FastAPI.

The filter API uses explicit resources for saved functions, workflows,
instances, and groupings. Runner execution endpoints will be documented
separately after the read API is settled.

Runner forms and the function editor's building-block palette are maintained
by the frontend. They are small, closed sets that need custom interfaces, so
the API does not expose runner or function-type metadata endpoints.

## General conventions

- All endpoints require authentication.
- An inaccessible resource is reported as not found so callers cannot use the
  API to discover resource identifiers.
- Workflow access is inherited by its instances, groupings, and group
  assignments. Those resources do not have independent permission models.
- A non-administrator may access a workflow only when they are an owner or
  editor of every associated novel and a contributor to every associated
  label group.
- Collection responses are paginated.
- `limit` defaults to `50` and may not exceed `100`.
- UUID-keyset collections use an opaque `cursor`. Aggregated group values use
  `offset`, because their ordering is based on a calculated value and count.
- Public response fields use the repository's existing camel-case aliases.

## Function registry

### `GET /filters/functions`

Return a paginated list of saved function definitions available to the current
user.

Supported query parameters:

- `search`: case-insensitive namespace or function-name search;
- `namespace`: exact namespace filter;
- `limit` and `cursor`: pagination.

This endpoint searches the general function library. Compatibility with a
particular workflow and runner is handled by the workflow-scoped endpoint
below.

### `GET /filters/functions/{functionDefinitionId}`

Return one saved function definition, including its serialized AST and
computed signature.

Function definitions do not currently have a finalized ownership model. The
initial read implementation may expose the shared function registry to every
authenticated user who can access filter workflows; mutation permissions will
be specified with the write endpoints.

### `GET /filters/workflows/{workflowId}/compatible-functions`

Return saved function definitions compatible with the workflow's schema and a
selected runner.

Supported query parameters:

- `runtimeName`: exact runtime discriminator, initially `python`;
- `runnerName`: exact runner discriminator, such as `map`, `filter`, or
  `group`;
- either `namespace` or `search` must be supplied so the backend does not scan
  the entire function registry;
- `limit` and `cursor`: pagination.

The database query first narrows the candidates by namespace or search term.
The backend then applies its existing type system to those candidates. This
keeps compatibility logic out of the frontend without attempting to encode
the symbolic type system as a SQL function or index.

## Workflows

### `GET /filters/workflows`

Return workflows accessible to the current user.

Supported query parameters:

- `novelId`: workflows associated with the novel;
- `labelGroupId`: workflows associated with the label group;
- `useCase`: server-managed use case, initially `advanced` or `glossary`;
- `status`: workflow status filter;
- `search`: case-insensitive workflow-name search;
- `limit` and `cursor`: pagination.

Each list entry contains at least the workflow ID, name, use case, schema,
status, message, associated novel IDs, associated label-group IDs,
creation/update timestamps, and an instance count.

`useCase` is assigned by the backend according to the feature that created the
workflow. It is not an arbitrary user-editable tag. Ordinary feature surfaces,
such as a Glossary tab, can query their own use case while the Advanced tab can
expose raw workflow operations.

### `GET /filters/workflows/{workflowId}`

Return one workflow with its use case, schema, status, message, permission
scope, and instance count.

The response includes `novelIds` and `labelGroupIds` for display and
navigation. Clients cannot modify these associations directly; runner services
derive and propagate them from source resources.

### `GET /filters/workflows/{workflowId}/instances`

Return workflow instances ordered by instance ID using keyset pagination.

Supported query parameters:

- `limit` and `cursor`: pagination.

Each entry contains `instanceId` and the typed `value` object. Complex
filtering across multiple groupings is intentionally not encoded into this GET
endpoint. Use the workflow query endpoint below for that operation.

### `POST /filters/workflows/{workflowId}/instances/query`

Perform a read-only, paginated instance query using values selected from any
subset of the workflow's groupings. A POST is used because typed, nested
multi-group filters do not fit safely or clearly into query parameters.

Request body:

```json
{
  "groupFilters": [
    {
      "groupingId": "00000000-0000-0000-0000-000000000000",
      "values": [
        { "type": "string", "value": "Alice" },
        { "type": "string", "value": "Bob" }
      ]
    },
    {
      "groupingId": "00000000-0000-0000-0000-000000000001",
      "values": [{ "type": "bool", "value": true }]
    }
  ],
  "limit": 50,
  "cursor": null
}
```

Values within one grouping are combined with OR. Different grouping filters
are combined with AND. An empty `groupFilters` list is equivalent to the
unfiltered workflow instance endpoint. Each grouping must belong to the
workflow and be complete before it can be queried. Values must match the
grouping's declared scalar output type.

The response uses the same instance representation and opaque keyset cursor as
`GET /filters/workflows/{workflowId}/instances`. It additionally returns each
selected grouping's value for every row so the frontend can render those
values as table columns without issuing per-instance requests.

### `GET /filters/workflows/{workflowId}/groupings`

Return the groupings attached to a workflow.

Supported query parameters:

- `status`: grouping status filter;
- `limit` and `cursor`: pagination.

Each entry contains the grouping ID, function definition summary, status,
message, job ID, and timestamps.

## Groupings

### `GET /filters/groupings/{groupingId}`

Return one grouping with its workflow ID, function definition, output type,
status, message, and assignment count.

Permission is determined exclusively through the grouping's workflow.

### `GET /filters/groupings/{groupingId}/values`

Return distinct grouping values and their instance counts.

Supported query parameters:

- `search`: textual search for string-valued groupings; rejected for numeric
  and boolean groupings;
- `limit` and `offset`: pagination.

Values retain their declared scalar type rather than being returned as display
strings.

## Existing selector endpoints

Runner forms should reuse existing NovelTL read APIs for resource selectors
where possible, including novel and label-group listing endpoints. Filter
endpoints are added only when selection requires filter-specific compatibility
logic, such as choosing a function compatible with a workflow and runner.

## Workflow use-case limitation

The current database `Workflow` model represents one materialized processing
stage, while a pre-rolled feature such as a glossary may eventually comprise
several stages. Initially, the use case can identify the user-facing or final
stage. If presets need to expose and manage several stages as one unit, they
will require a separate pipeline/run resource rather than overloading the
workflow use-case field.
