# Editor backend

**Last updated:** 2026-06-28

This is the first in a series of chapters that describes how editor works. This document details the backend architecture for the controller.

## Modifying data

The implementation on the backend for text/label editing is inspired by [Operational Transforms](https://en.wikipedia.org/wiki/Operational_transformation). This project uses a custom built protocol and a custom implementation.

We have also considered having the user send the entire text/label data to save. This has the caveat that the backend has no certainty that the user has seen any of the existing data on the frontend as a certificate that the user know what is going on already. Hence we have decided to limit the amount of communication that the frontend can send to the backend. This also has the added benefit of smaller HTTP payloads, but it makes the implementation more challenging.

### Identifying text ranges

Recall in the data model for a label, a given label can be specified by its text range and its label data. For label identification, we will always mandate any API request to send the text in the corresponding text range. As an example, if we have the text "abcdefg" and we wish to identify the text "def", the corresponding identifier would look something like 
```json
{
    "chapterContentId": "[uuid of chapter content]",
    "start": 3,
    "text": "def"
}
```
We will call such an identifier a **text position identifier**.

For a label operation we additionally need to know which label data it targets. The label data is identified by the `labelDataId` path parameter of the endpoint (`PATCH /label-datas/{labelDataId}`) rather than a field inside the operation; the operation body itself carries the text-range identifier. We will call the combination a **label identifier**.

Note that the exact keys vary by context. A label operation identifies its range with `startPos`, `endPos`, and `word` (the backend schema fields are `start_pos`, `end_pos`, `word`), and the corresponding columns on a stored label are `label_start`, `label_end`, and `label_word`. Read the schemas for details on exactly what is used where.

The backend will then validate any operation that sends an identifier with the following expression (note that `end_pos == start_pos + len(word)` is enforced by the schema):
```python
text[start_pos : end_pos] == word
```

As an example, if we need to validate that there exists a label with said identifier in some label data, then we can perform an SQL query of the form
```sql
SELECT * FROM labels
WHERE labels.label_start = [start_pos]
AND labels.label_word = [word]
AND labels.label_data_id = [labelDataId];
```
and check if our query returns nonempty data.

This identification method will apply to both text operations and label operations. Namely, this ensures two things:

1. The end user knows what data is at the position that they wish to modify at the time that they send the request.
2. We will see that (with some modification) this guarantees that any text/label operation is reversible.

These identifiers will be used throughout both the frontend and backend extensively to validate operations.

### Label operations

See [backend/src/labels](../../backend/src/labels/) for details.


A label operation is either an add operation, a delete operation, or an update operation. Specifically, 

- An add operation is simply a JSON payload that has fields for a label identifier and fields for metadata associated with the label.
- An update operation is a JSON payload that has fields for a label identifier corresponding to an existing label and metadata for the new desired label. This includes metadata to update the label position, which means that an update operation should contain an optional second label identifier.
- A delete operation is simply a JSON payload with a label identifier.

Broadly speaking, processing a single label operation will always follow the following format:

1. Fetch chapter content + corresponding label data from database into memory
2. Check if label operation is valid (is there an existing label with the given identifier? does performing this operation leave the data in an invalid state?)
3. Send an SQL request to the database
4. Commit to database

Note that errors can happen on step 4 due to race conditions when users simultaneously edit a single label data. In that case, we rollback the transaction and throw an error. In fact, in this case, users may experience desynchronization even while the data model stays consistent on the backend and furthermore, their respective operations may still succeed if they are not working on the same part of a label data. For now we will keep this "feature" as a necessary evil. 

Performing a single operation at a time is relatively inefficient - consider what would happen if the user performs a lot of label operations in a lot of different places - the frontend would need to send one HTTP request for each desired label operation. We hence adopt the practice of receiving lists of label operations instead of single label operations. Hence steps 2 and 3 in the algorithm above are really coralled into a for loop over all label operations in an HTTP request.

The specific algorithm can be found at the endpoint `PATCH /label-datas/${labelDataId}`. 

### Text operations

There are two types of text operations a user can perform (the `op` field is the literal `"insert"` or `"delete"`):

- An insert operation takes a text position and a text and simply inserts that text at that position.
- A delete operation takes a text position identifier and deletes the text at that position.

Compared to label operations, it is more important that end users have a consistent view of the text. This is because a text operation should semantically modify all labels for that chapter. We follow the semantics below for deciding what happens to labels after a text operation:


- For insert operations:
    - Any label that ends before the start of an insert operation should remain in the same position
    - Any label that contains the start position of the insert operation should be deleted
    - Any label that starts after the start position of the insert operation should be shifted right by the length of the text added
- For delete operations:
    - Any label that ends before the start position of the delete operation should remain in the same position
    - Any label whose range overlaps with the delete range should be deleted
    - Any label whose start position is after the end position of the delete operation should be shifted left by the corresponding length of text being deleted

To ensure a consistent data model, we store text data in chapter content snapshots (see the `chapter_contents` table for details). The idea here is to have a list of immutable chapter contents for each chapter, where each chapter content has an associated version and id. Furthermore, the version attribute should be unique for each chapter id (enforced by a `UniqueConstraint` on the database). The frontend should keep track of the latest chapter content id (chapter content id with the latest version). 

When any update comes through, the frontend should send its copy of the chapter content id it is working with and the backend should verify that the chapter content associated with this id is the latest version for the corresponding chapter. Any updates performed to the database should then be in the form of inserting new chapter contents with version being one more than the previous max version. If any of these operations fail, it is most likely due to a race condition and the backend should roll back the corresponding database transaction and notify the frontend.

To ensure that the labels are also copied over, the backend should copy over all existing label datas and perform the corresponding operations as well. We can also "stream" these text operations, just like the label operations. To summarize, the backend should follow the following algorithm when performing text operations:

1. Fetch chapter content that satisfies that has both the latest version and corresponding chapter content id and keep an in-memory copy of the text, or throw an error if no such chapter content exists
2. Fetch all label datas corresponding to this chapter content id
3. Fetch all labels corresponding to any of the label datas specified above and keep an in-memory copy of a mapping `label data id : list of labels`
4. For each text operation:
    - Modify the in-memory text accordingly
    - Modify the in-memory labels accordingly (see semantics above)
5. Create a new chapter content with `version = current version + 1` and get uuid, or throw an error (race condition can happen here with version conflict)
6. Create a new label data for each label data in the in-memory mapping corresponding to the new chapter content id
7. Insert the in-memory labels corresponding the the new label datas

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'primaryColor': '#1e293b', 'primaryTextColor': '#e2e8f0', 'primaryBorderColor': '#334155', 'lineColor': '#94a3b8', 'secondaryColor': '#0f172a', 'tertiaryColor': '#1e293b'}}}%%
sequenceDiagram
    participant C as Client
    participant B as Backend
    participant D as Database

    C->>B: PATCH /chapters/{id}/content<br/>{chapterContentId, textOps: [{op, start, text}, ...]}
    B->>D: Fetch chapter_content<br/>WHERE id = expectedId AND version = MAX(version)
    alt Version mismatch (race condition)
        B-->>C: 409 Conflict (outdated)
    else Chapter content found
        B->>D: Fetch all label_datas for chapter_content_id
        B->>D: Fetch all labels for each label_data
        Note over B: In-memory: apply text ops<br/>followed by label shift/delete semantics
        B->>D: INSERT new chapter_content<br/>(version = prev + 1)
        alt Version conflict on insert
            B->>D: ROLLBACK
            B-->>C: 409 Conflict
        else Success
            B->>D: INSERT new label_datas<br/>(one per old label_data, linked to new chapter_content)
            B->>D: INSERT updated labels<br/>(linked to new label_datas)
            B->>D: COMMIT
            B-->>C: 200 OK {new chapterContentId, version, labelDataIdMap}
        end
    end
```

### Other operations

These include creating new chapters/new label groups. These are fairly straightforward and will not be outlined in this document.

## Caching requests

Consider what may happen if a client has bad connection due to whatever reason. It may be the case that their HTTP requests are dropped occasionally. What may be more catastrophic is if the backend receives a client's HTTP request, performs the (non-idempotent) operation, and the response is dropped midway. The client then has no knowledge about whether their request went through or not.

Without the feature that we will explain below, the client has two options:

1. Retry the same request. This may perform an additional unintended operation on the backend and leave the data on the frontend in an inconsistent state with the backend.
2. Force a refresh. This will keep the data in a consistent state, but will consume an expensive operation and may disrupt the workflow of the user.

To mitigate this problem, we will temporarily store request *results* in a Redis cache. For certain editor requests, the frontend may send a uuid query parameter called `requestKey`. If a `requestKey` is received, the backend stores a cache entry keyed by that `requestKey` with a short TTL. The entry is a small record of the form:

```python
{
    "status": "pending" | "success" | "failure",
    "status_code": int | None,   # the HTTP status the original request resolved to
    "response": dict | None,      # the serialized success payload, if any
    "error": { "detail": ..., "cacheConflict": bool } | None,
}
```

Note that the request body itself is **not** stored — only the status, the resolved status code, the success response, and any error. The entry shape lives in [backend/src/requests/cache.py](../../backend/src/requests/cache.py).

A request that uses this feature follows this workflow:

1. If no `requestKey` is provided, process the request normally (no caching).
2. If a `requestKey` is provided:
    - Atomically insert `requestKey -> {status: "pending", ...}` into Redis (a set-if-absent). If the key already exists, the request is a duplicate: reject it with a **409** whose body sets `cacheConflict: true`.
    - Otherwise process the request. On success, overwrite the entry with `{status: "success", status_code, response}`. On an `HTTPException`, overwrite it with `{status: "failure", status_code, error}` and re-raise. (A genuine 409 from the handler is re-surfaced with `cacheConflict: false`, so the client can distinguish a real conflict from a duplicate-key collision.)

This workflow is implemented as a pair of decorators in [backend/src/requests/decorators.py](../../backend/src/requests/decorators.py) — `ttl_cache` for synchronous endpoints and `attl_cache` for async endpoints — together with an `svp` helper that serializes the success payload. Cached editor endpoints include `POST /label-groups`, `POST /label-groups/{labelGroupId}/label-datas`, `PATCH /label-datas/{labelDataId}`, and `PATCH /chapters/{chapterId}/content`.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'primaryColor': '#1e293b', 'primaryTextColor': '#e2e8f0', 'primaryBorderColor': '#334155', 'lineColor': '#94a3b8', 'secondaryColor': '#0f172a', 'tertiaryColor': '#1e293b'}}}%%
sequenceDiagram
    participant C as Client
    participant B as Backend
    participant R as Redis Cache

    C->>B: POST /label-groups?requestKey=uuid<br/>{ ...body... }
    B->>R: SET uuid = {pending} if absent
    alt requestKey already present (duplicate)
        B-->>C: 409 Conflict {cacheConflict: true}
    else first time
        B->>B: Process request
        alt Success
            B->>R: SET uuid = {success, status_code, response}
            B-->>C: 200 OK + response
        else Failure
            B->>R: SET uuid = {failure, status_code, error}
            B-->>C: 4xx/5xx Error
        end
    end

    Note over C,B: If the response is lost (timeout)...
    C->>B: GET /cached/{uuid}
    B->>R: GET uuid
    alt key found
        B-->>C: 200 OK + cache entry<br/>(client reads status from body)
    else key not found (TTL expired / lost)
        B-->>C: 404 Not found
        Note over C: Regenerate key and resend
    end
```

A client can then poll the status of a request it previously sent by querying its `requestKey`. The poll endpoint (`GET /cached/{requestKey}`) returns the cache entry with a `200` when the key is present and a `404` when it is missing; the client branches on the entry's `status` field. The full sequence is:

1. Generate a collision-resistant key (uuid) and send the request with this request key.
2. If the client receives a successful response, then all is well.
3. If the client receives a response that the backend failed to process the request, it knows that its request must be invalid in some way (or an internal server error happened, in which case there might be a bug).
4. If the client does not receive a response/the client times out, then it can poll the request key.
    - `status: "pending"` — the request is still being processed, so the client waits.
    - `status: "failure"` — the request was invalid somehow, similar to a regular failure.
    - `status: "success"` — all is well, and the cached `response` can be used.
    - `404` (key does not exist) — either the TTL expired in Redis (this should not happen with proper frontend controls), or the request was lost on the way from frontend -> backend. In this case the frontend regenerates a request key and resends the request. (Resending with the *same* key would instead hit the duplicate-key `cacheConflict` 409 described above.)

We will see in the subsequent chapters that this is almost exactly the workflow that the frontend adopts.