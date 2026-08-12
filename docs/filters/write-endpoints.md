# Filter write API specification

> **Status:** Implemented.

This document defines the first filter write API. It should be sufficient for
another coding agent to implement the public schemas, service functions,
routes, dependency wiring, and tests without redesigning the API. Existing
read endpoints are documented in [endpoints.md](endpoints.md).

## Scope

| Method | Path | Success | Purpose |
| --- | --- | --- | --- |
| `POST` | `/filters/functions/validate` | `200` | Validate a function draft without saving it |
| `POST` | `/filters/functions` | `201` | Save an immutable function definition |
| `PATCH` | `/filters/workflows/{workflowId}` | `200` | Rename or clear a workflow name |
| `PATCH` | `/filters/instances/{instanceId}` | `200` | Update mutable fields on one instance |
| `POST` | `/filters/runners/python/label-source` | `202` | Materialize labels as a new workflow |
| `POST` | `/filters/runners/python/annotation` | `202` | Add mutable fields to an existing workflow |
| `POST` | `/filters/runners/python/map` | `202` | Map a function into a new workflow |
| `POST` | `/filters/runners/python/filter` | `202` | Filter into a new workflow |
| `POST` | `/filters/runners/python/group` | `202` | Create grouping assignments |

Function update/delete, workflow or grouping deletion, retry, assignment
mutation, and runner-metadata endpoints are out of scope. All JSON fields use
the repository's camel-case aliases.

## Public versus internal runner models

Each operation has its own public endpoint, request, and response. Public
requests must not accept `runtimeName`, `runnerName`, generated job IDs,
output workflow IDs, or grouping IDs.

The existing discriminated `RunnerInput` union remains internal:

```text
public request
  -> operation service validates and creates target
  -> internal RunnerInput with generated IDs
  -> dispatcher -> Celery task -> worker
```

The internal payloads are `PythonLabelSourceInput(label_group_id,
output_workflow_id)`, `PythonAnnotationInput(workflow_id, new_fields)`,
`PythonMapInput(source_workflow_id, output_workflow_id,
function_definition_id)`, `PythonFilterInput(source_workflow_id,
output_workflow_id, function_definition_id)`, and `PythonGroupInput(grouping_id)`.

## Function creation

### `POST /filters/functions/validate`

Request model: `ValidateFunctionDefinitionRequest`.

```json
{
  "functionDefinition": { "name": "literalString", "value": "Alice" }
}
```

Parse the AST with the existing `function_adapter` and return its computed
signature. This endpoint is authenticated but does not read or write the
database, check registry-name conflicts, or require a namespace and function
name. Invalid serialized ASTs return `422` with the standard Pydantic error
body.

Response model: `FunctionDefinitionValidationResponse`.

```json
{
  "signature": {
    "args": [],
    "output": { "kind": "field", "type": "string", "mutable": false }
  }
}
```

### `POST /filters/functions`

Request model: `CreateFunctionDefinitionRequest`.

```json
{
  "namespace": "glossary",
  "functionName": "character-name",
  "functionDefinition": { "name": "literalString", "value": "Alice" }
}
```

- `namespace`: required non-empty string, at most 100 characters.
- `functionName`: required non-empty string, at most 100 characters.
- `functionDefinition`: required serialized function AST object.

Parse the AST with the existing `function_adapter` before insertion. Persist
the parsed model using JSON mode, camel-case aliases, and excluded computed
fields. Client-supplied computed fields such as signatures should fail the
model's extra-field validation rather than being persisted. Return the
existing `FunctionDefinitionResponse`.

Definitions are immutable. The database has no function owner/scope model, so
v1 creation is available to every authenticated user and writes to the shared
registry. The unique `(namespace, function_name)` key defines identity; a
collision returns `409`. User-owned functions require a later schema and
permission design.

## Workflow rename

### `PATCH /filters/workflows/{workflowId}`

Request model: `RenameWorkflowRequest`.

```json
{ "workflowName": "Named character candidates" }
```

`workflowName` is a string of at most 100 characters or `null`; `null` clears
the name. No other workflow field is mutable through this request. Apply
`workflow_mod_access_update`; missing and inaccessible workflows return `404`.
Renaming is valid in every execution status. Return `WorkflowResponse`.

## Instance update

### `PATCH /filters/instances/{instanceId}`

Request model: `UpdateInstanceRequest`.

```json
{
  "fields": {
    "reviewNote": { "kind": "value", "type": "string", "value": "Needs revision" },
    "confidence": { "kind": "value", "type": "float", "value": 0.72 }
  }
}
```

`fields` contains between 1 and 100 entries. Values use `MDataType`, so only
string, integer, float, and boolean values are accepted. The service hides
missing and inaccessible instances behind `404`, locks the workflow and
instance together, and requires the workflow to be complete. Every requested
field must exist in the workflow schema, be mutable, and have the same scalar
type as the supplied value.

Validation is all-or-nothing. On success, one JSONB update merges the supplied
fields into the instance's existing `fields` object without replacing
unspecified fields. Return the updated `InstanceResponse`. Concurrent writes to
the same instance serialize through its row lock; queueing serializes through
the workflow lock.

## Accepted-operation responses

Label source, annotation, map, and filter return `WorkflowOperationAccepted`:

```json
{
  "jobId": "00000000-0000-0000-0000-000000000001",
  "workflow": {
    "workflowId": "00000000-0000-0000-0000-000000000002",
    "workflowName": "Named character candidates",
    "useCase": "advanced",
    "schema": { "fields": {} },
    "jobId": "00000000-0000-0000-0000-000000000001",
    "workflowStatus": "pending",
    "workflowMessage": null,
    "novelIds": [],
    "labelGroupIds": [],
    "instanceCount": 0,
    "createdAt": "2026-08-03T00:00:00Z",
    "updatedAt": "2026-08-03T00:00:00Z"
  }
}
```

`workflow` is the existing `WorkflowResponse`. The repeated operation-level
job ID identifies the accepted operation; `workflow.jobId` describes current
resource state.

Group returns `GroupOperationAccepted`:

```json
{
  "jobId": "00000000-0000-0000-0000-000000000003",
  "grouping": {
    "groupingId": "00000000-0000-0000-0000-000000000004",
    "workflowId": "00000000-0000-0000-0000-000000000002",
    "functionDefinition": {
      "functionDefinitionId": "00000000-0000-0000-0000-000000000005",
      "namespace": "glossary",
      "functionName": "character-name"
    },
    "outputType": "string",
    "jobId": "00000000-0000-0000-0000-000000000003",
    "groupingStatus": "pending",
    "groupingMessage": null,
    "assignmentCount": 0,
    "createdAt": "2026-08-03T00:00:00Z",
    "updatedAt": "2026-08-03T00:00:00Z"
  }
}
```

`grouping` is the existing `GroupingResponse`.

## Label source

### `POST /filters/runners/python/label-source`

Request model: `PythonLabelSourceRequest`.

```json
{
  "labelGroupId": "00000000-0000-0000-0000-000000000010",
  "outputName": "Current character labels"
}
```

`outputName` is optional, nullable, and at most 100 characters. Before
creation, verify the label group exists and is accessible. A non-admin must be
an owner/editor of its novel and a label-group contributor. Missing and
inaccessible both return `404`.

Create a new workflow with a generated workflow ID and the output name,
`use_case = advanced`, `LABEL_SOURCE_SCHEMA`, a null message, one
`WorkflowNovel` association for the label group's novel, and one
`WorkflowLabelGroup` association for the group. Dispatch
`PythonLabelSourceInput`; return `WorkflowOperationAccepted`.

## Annotation

### `POST /filters/runners/python/annotation`

Request model: `PythonAnnotationRequest`.

```json
{
  "workflowId": "00000000-0000-0000-0000-000000000020",
  "newFields": {
    "reviewNote": { "type": "string", "defaultValue": "" },
    "confidence": { "type": "float", "defaultValue": 0.0 }
  }
}
```

The workflow must exist, be accessible, and be complete. Field names must be
new to the workflow, and the resulting schema may not exceed the schema field
limit. The operation reserves that existing workflow in place, dispatches
`PythonAnnotationInput`, and returns it as pending. The runner adds every field
to the schema as mutable and adds its requested default value to every existing
instance.

## Map

### `POST /filters/runners/python/map`

Request model: `PythonMapRequest`.

```json
{
  "sourceWorkflowId": "00000000-0000-0000-0000-000000000020",
  "functionDefinitionId": "00000000-0000-0000-0000-000000000021",
  "outputName": "Projected names"
}
```

`outputName` is optional, nullable, and at most 100 characters. Validate that:

- the source exists, is accessible through `workflow_mod_access_select`, and
  is `complete`;
- the function exists and its persisted AST parses;
- it accepts exactly one object schema;
- the source schema extends its required input schema;
- it returns an object schema.

Create a new `advanced` workflow whose schema is the function output.
Copy all `WorkflowNovel` and `WorkflowLabelGroup` associations from source to
output. Dispatch `PythonMapInput`; return `WorkflowOperationAccepted`.

## Filter

### `POST /filters/runners/python/filter`

Request model: `PythonFilterRequest`.

```json
{
  "sourceWorkflowId": "00000000-0000-0000-0000-000000000020",
  "functionDefinitionId": "00000000-0000-0000-0000-000000000022",
  "outputName": "High-confidence names"
}
```

The fields have the same public meaning as map. Validate that:

- the source exists, is accessible, and is `complete`;
- the function exists and parses;
- it accepts exactly one object schema;
- the source schema extends its required input schema;
- it returns a boolean field.

Create a new `advanced` workflow whose schema exactly equals the source
schema. Copy all novel and label-group associations. Dispatch
`PythonFilterInput`; return `WorkflowOperationAccepted`.

## Group

### `POST /filters/runners/python/group`

Request model: `PythonGroupRequest`.

```json
{
  "workflowId": "00000000-0000-0000-0000-000000000020",
  "functionDefinitionId": "00000000-0000-0000-0000-000000000023"
}
```

Validate that:

- the workflow exists, is accessible, and is `complete`;
- the function exists and parses;
- it accepts exactly one object schema;
- the workflow schema extends its required input schema;
- every required workflow field is immutable;
- it returns an immutable string, integer, or boolean field.

Create a new grouping with a generated grouping ID, a null message, and
the requested workflow/function IDs. It inherits access from its workflow and
does not copy associations. Dispatch `PythonGroupInput`; return
`GroupOperationAccepted`.

The database permits only one grouping per `(workflowId,
functionDefinitionId)` pair. A duplicate returns `409`.

## Transaction and dispatch lifecycle

Database creation and broker publication are not atomic. Use this v1 sequence:

1. Validate request and permissions.
2. Generate target and job IDs.
3. Insert the new target and required associations.
4. Atomically queue the complete job member set under the generated job ID.
5. Commit the database transaction.
6. Call `RunnerDispatcher.enqueue(job_id, internal_input)`.
7. Return the enriched pending resource with `202`.

If publication raises `RunnerEnqueueFailedException`, atomically abort the
whole pending job to `failed`, store one concise publication-failure message,
commit, and return `503`.

Workers claim the complete persisted member set by job ID. Their validation
remains defense against malformed internal messages and database drift.

V1 has no request idempotency key. Retrying after an ambiguous client/network
failure can create another target. Add a persisted request key later if safe
automatic retries are needed; never infer idempotency from `outputName`.

## Error contract

Use the standard `{ "detail": "..." }` body.

| Status | Meaning |
| --- | --- |
| `400` | Function/workflow schemas are incompatible or the operation is semantically invalid |
| `404` | A referenced resource is missing or inaccessible |
| `409` | A workflow is not complete, a unique resource conflicts, or state prevents the operation |
| `422` | Request fields or serialized AST fail structural validation |
| `503` | Publication failed and the newly created target was marked failed |

Translate unique-constraint races into `409`. Never reveal whether an
inaccessible resource exists.

## OpenAPI requirements

- Define public Pydantic request/response models. The AST may be a JSON object
  because it is explicitly parsed with `function_adapter`.
- Give resource-ID fields `Field(description=...)` metadata, especially
  `sourceWorkflowId`, for generated frontend and MCP forms.
- Declare response models and errors on each route.
- Keep five distinct runner operations. Do not expose a generic execute route
  or the internal discriminated union publicly.
- Use stable operation IDs: `create_filter_function`,
  `validate_filter_function`, `rename_filter_workflow`,
  `update_filter_instance`,
  `run_python_label_source`, `run_python_annotation`, `run_python_map`,
  `run_python_filter`, and `run_python_group`.

## Required tests

Add service and HTTP tests for:

- successful creation and response shape for every endpoint;
- five distinct OpenAPI runner schemas and stable operation IDs;
- AST validation and function-name conflicts;
- side-effect-free draft validation and its computed signature;
- rename, clearing the name, and inaccessible workflows;
- missing and inaccessible sources producing the same response;
- source status and runner function/schema validation;
- association creation and propagation;
- grouping uniqueness;
- exact internal `RunnerInput` passed to a recording dispatcher;
- dispatch only after target commit;
- enqueue failure aborting the whole pending job and returning `503`;
- no dispatch after failed validation or authorization.

Retain the existing dispatcher serialization/task tests. HTTP tests should
override dispatcher dependency injection instead of contacting the broker.
