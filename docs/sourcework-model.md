# SourceWork Model and Permissions

**Last Updated**: April 04, 2026
**Status**: Draft

This document defines the SourceWork architecture for grouping related novels and the current one-pass chapter/revision model restructure strategy. Read this if you are implementing SourceWork database changes, chapter content versioning changes, or permission checks.

---

## Table of Contents

1. [Background and Goals](#background-and-goals)
2. [Theory and Motivation](#theory-and-motivation)
3. [Core Decisions](#core-decisions)
4. [Naming Direction](#naming-direction)
5. [Data Model Proposal](#data-model-proposal)
6. [Permissions Contract](#permissions-contract)
7. [Discovery Query Semantics](#discovery-query-semantics)
8. [API Contract Draft](#api-contract-draft)
9. [Workflow and UX Implications](#workflow-and-ux-implications)
10. [Backend Refactor Surface](#backend-refactor-surface)
11. [Non-Goals and Deferred Items](#non-goals-and-deferred-items)
12. [Implementation Phases](#implementation-phases)
13. [Open Decisions](#open-decisions)
14. [Relevant Files](#relevant-files)
15. [See Also](#see-also)

---

## Background and Goals

Historically, the system modeled content as `Novel -> Chapter -> Revision -> RevisionText`. The active implementation direction is a one-pass model restructure to `SourceWork -> Novel -> Chapter -> ChapterContent`, while keeping text versioning semantics for label integrity and concurrency safety.

Primary goals:
1. Group related novels (for example, source and translations) under one parent resource.
2. Keep novel-level permissions authoritative.
3. Avoid introducing implicit ownership inheritance from the new grouping layer.
4. Preserve text versioning behavior during the one-pass rename/restructure.

### Current implementation note

The backend service/schemas/permissions/model layers are being migrated in one pass. Router updates are intentionally deferred to a follow-up step after the core rename/restructure commit to reduce moving pieces during the data-model migration.

## Theory and Motivation

The core idea is to separate three concerns that are currently entangled:

1. **Source grouping** - which novels belong to the same underlying work.
2. **Content ownership** - who can edit or publish a specific novel.
3. **Text history** - how the chapter text evolves over time.

The current implementation already solves text-history safety reasonably well by versioning text and keeping label anchors tied to a specific text snapshot. The part that is still conceptually noisy is the chapter/revision split and the lack of a first-class grouping model for multiple novels that belong to the same source material.

The practical reason this matters is that the backend currently serves two different product truths:

1. The frontend wants a single navigable "work" that contains multiple novels, languages, or editions.
2. The backend wants to preserve strict access control and revision history without letting those concerns leak into each other.

SourceWork is the boundary between those two truths. It lets the UI ask "what belongs together?" without requiring the permissions layer to answer "who can edit this exact novel?" from the grouping layer alone.

This is also why the refactor space opens up once the frontend works: after the UI proves the grouping workflow, the backend can be simplified aggressively around the actual invariant we care about, rather than around historical implementation convenience.

## Core Decisions

This document captures the following decisions from architecture discussion:

1. Introduce `SourceWork` as metadata and grouping resource.
2. Keep text versioning at the chapter-content layer for concurrency and label safety.
3. Move from revision-oriented naming to chapter-content naming in backend internals.
4. Remove `revision_is_primary` and `revision_is_public` in favor of chapter-level publication state.
5. Default discovery should list `SourceWork` items only when at least one child novel is visible to the requesting actor.
6. AutoLabel creation policy target remains: any user with read access to the novel.
7. Label group creation policy target remains: any user with novel access.

## Backend Refactor Surface

Once the frontend workflow is stable, the backend has a few clean refactor targets that become available at the same time:

1. **Collapse chapter and revision metadata** if the product no longer needs them as separate user-facing concepts.
2. **Rename text-version entities** to make the text-history layer explicit instead of revision-oriented.
3. **Centralize grouping semantics** in SourceWork instead of encoding them indirectly through novel relationships.
4. **Simplify discovery queries** by making SourceWork the thing users discover first, and novels the thing they open second.
5. **Reduce permission ambiguity** by keeping novel ownership authoritative and not teaching the grouping layer to impersonate it.

### Current model versus target model

| Current model | Target model | Why it changes |
|---|---|---|
| `Novel -> Chapter -> Revision -> RevisionText` | `SourceWork -> Novel -> Chapter -> ChapterContent` | Makes the text-history layer explicit while collapsing the unnecessary chapter/revision split |
| `revision_is_primary` / `revision_is_public` on revision metadata | Removed; chapter publication state is tracked on `Chapter.chapter_is_public` | The fields become redundant after collapsing chapter/revision metadata |
| Revisions as the main UI selection concept | Novel or chapter text version as the user-facing unit | The UI no longer needs to ask the user to choose among artificial revision layers |
| Discovery by novel or chapter context first | Discovery by SourceWork first, then Novel, then Chapter | Better matches grouped source material and cross-translation browsing |
| Permission helpers tied to revision-oriented joins | Permission helpers tied to novel and chapter-text-version joins | Keeps access checks aligned with the actual entity boundaries |

### What the backend can simplify

Once the frontend proves the grouped workflow, the backend can drop several pieces of incidental complexity:

1. **Remove fake multiplicity** - if there is no meaningful branch of chapter metadata, keep one canonical chapter row per chapter number.
2. **Reduce selection state** - if the UI no longer needs revision picking, the backend does not need to support that as a core navigation primitive.
3. **Clarify task scope** - AutoLabel, filters, and label operations can target the exact chapter text version the user chose.
4. **Make group navigation first-class** - SourceWork becomes the way to answer "what belongs together?" without overloading novel permissions.
5. **Leave future branching explicit** - if the product ever needs alternate chapter variants, add a branching concept intentionally rather than preserving revision as a hidden surrogate for branches.

The reason this feels like "a lot of refactors" is that the backend has been acting as the keeper of several historical assumptions at once. Once the frontend demonstrates that users want grouped discovery plus simpler chapter navigation, those assumptions can be separated into cleaner units. That usually reveals more refactor opportunities than expected, because you can now remove code that existed only to reconcile those old assumptions.

### Refactor opportunities that fall out naturally

These are the most likely backend cleanups after the model is simplified:

1. Replace revision-centric query builders with chapter-text-version query builders.
2. Collapse duplicate permission logic that currently exists only because chapter and revision are both carrying meaning.
3. Simplify label and autolabel foreign key paths so they point at one clear text-history entity.
4. Replace "primary revision" conventions with explicit canonical chapter semantics.
5. Simplify API request payloads so the frontend no longer needs to carry revision selection state everywhere.

The important implementation lesson is that the backend should not be refactored just because the UI can now support a more unified experience. The refactor should follow the invariant, not the interface. If the invariant is "one canonical chapter per chapter number inside a novel, with versioned chapter text," then the backend should be reshaped around that directly instead of preserving a historical split that no longer carries its weight.

This is the same pattern that made the text-editing work viable in [editable-with-labels.md](editable-with-labels.md): once the project names the actual invariant and encodes it explicitly, a lot of incidental complexity becomes removable.

## Naming Direction

The preferred naming direction is:

1. `SourceWork` - source-material grouping metadata.
2. `Novel` - concrete edition/translation variant in a group.
3. `Chapter` - chapter metadata (number, ownership to novel).
4. `ChapterContent` - active implementation name for versioned chapter text rows.

Notes:
1. The active backend migration is using `ChapterContent` as the canonical replacement for `RevisionText`.
2. Router endpoint naming and payload naming can be rewritten after the core rename/restructure commit.

## Data Model Proposal

### Minimal near-term model

Add `source_works` and connect novels to source works.

```sql
CREATE TABLE source_works (
    source_work_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_work_title VARCHAR(255) NOT NULL,
    source_work_description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

ALTER TABLE novels
ADD COLUMN source_work_id UUID REFERENCES source_works(source_work_id);
```

### Relationship rules

1. A `SourceWork` may have zero or more `Novel` rows.
2. A `Novel` may belong to zero or one `SourceWork` in the initial rollout.
3. Novel contributor relationships stay on the novel and are not moved to source works.

### Why the grouping model is separate from access control

The grouping layer is only useful if it can answer discovery questions cheaply and consistently. It should not become a second permission system.

The permission rule is therefore:

1. SourceWork may be visible as a container.
2. Novel access is still decided by the novel's own visibility and contributor relationships.
3. A user can discover a SourceWork because of one visible novel without gaining any authority over other novels in the same SourceWork.

That separation is important because it prevents group ownership from becoming an accidental superuser role.

### Optional future extension

If richer cross-linking is needed later:
1. `source_work_associations` for inter-source relationships.
2. `novel_associations` for intra-group novel relationship metadata.

These are deferred and not required for initial implementation.

## Permissions Contract

### Core principle

`SourceWork` is a discovery container. Novel-level access control remains the source of truth.

### Required behavior

1. `SourceWork` listing is filtered by visible child novels.
2. `SourceWork` detail should not leak hidden novels.
3. `SourceWork` membership must not grant novel edit privileges by default.
4. Novel contributor and visibility checks remain implemented through novel permission helpers.

### Implementation principle

Permission helpers for SourceWork should be shaped like the existing novel helpers:

1. Build SQL predicates, not post-query filtering.
2. Preserve zero-knowledge behavior where possible.
3. Reuse novel visibility checks instead of duplicating them.
4. Keep ownership and contributor logic separate from discovery grouping.

This is the key implementation detail: SourceWork queries should not ask "is this group public?" in isolation. They should ask "does this group contain at least one novel that this actor can actually see?"

That makes the query shape naturally align with the current access model and avoids inventing a new visibility hierarchy.

### Ownership model

Initial recommendation:
1. No `source_work_owner` role is required for V1 if source work metadata edits are admin-only.
2. If non-admin edits are needed later, add explicit source-work contributor roles that do not inherit to novels.

### Zero-knowledge compatibility

To preserve privacy posture:
1. A user should not infer hidden novels through source work responses.
2. Returning 404 for detail requests with no visible child novel is acceptable and consistent with current conventions.

## Discovery Query Semantics

The intended discovery query pattern is:

```sql
SELECT sw.*
FROM source_works sw
WHERE EXISTS (
    SELECT 1
    FROM novels n
    WHERE n.source_work_id = sw.source_work_id
      AND <novel_visibility_for_actor_predicate>
);
```

The actor predicate should reuse existing novel visibility and contributor logic (admin bypass, guest visibility floor, contributor checks).

## API Contract Draft

Proposed endpoints (draft):

1. `GET /source-works`
   - Returns source works with at least one visible child novel.
2. `GET /source-works/{source_work_id}`
   - Returns source work metadata plus only visible child novels.
   - Returns 404 if no visible child novel exists for requester.
3. `POST /source-works`
   - Creates metadata container.
4. `PATCH /source-works/{source_work_id}`
   - Updates metadata.
5. `POST /source-works/{source_work_id}/novels/{novel_id}`
   - Attach novel to source work (policy-controlled).
6. `DELETE /source-works/{source_work_id}/novels/{novel_id}`
   - Detach novel from source work (policy-controlled).

Near-term policy for attach/detach should require novel-level authority and must not allow arbitrary reassignment by users who only have read access.

## Workflow and UX Implications

1. Workspace discovery can pivot from "select novel first" to "select source work, then novel".
2. Cross-novel chapter navigation becomes feasible (for example, move to chapter `n + 1` in another novel within same source work when current novel is missing that chapter).
3. Existing chapter/revision workflows remain valid until explicit schema refactor is planned.
4. Revision selection persistence across sessions remains a frontend concern and is not solved by SourceWork alone.

### Why this still helps the workspace

The frontend currently has to reason about chapter selection, revision selection, and hidden variants at the same time. SourceWork does not remove that complexity entirely, but it gives the UI a better first pivot:

1. Show the grouped source material first.
2. Then let the user choose which novel variant they want.
3. Then let the chapter workflow behave as it already does.

That reduces the chance that the workspace feels like it is silently switching between unrelated copies of the same chapter.

If later you decide to keep only one canonical chapter per chapter number in each novel, SourceWork still remains useful because it continues to solve the inter-novel grouping problem independently of the text-history model.

## Non-Goals and Deferred Items

Not in initial SourceWork rollout:

1. Full replacement of revision model.
2. Immediate endpoint-level router path/parameter rewrite during the same commit as model-layer migration.
3. Automatic cross-novel permission inheritance.
4. Migration logic for production historical data (currently out of scope).

## Implementation Phases

### Phase 1: Schema and read APIs
1. Add `source_works` table.
2. Add nullable `novels.source_work_id` foreign key.
3. Implement list/detail endpoints with visibility-aware filtering.

### Phase 2: Write APIs and policy hardening
1. Implement create/update source work endpoints.
2. Implement attach/detach novel endpoints.
3. Add permission tests for all source-work endpoints.

### Phase 3: Router and UI integration
1. Rewrite router endpoints and request/response naming to chapter-content terminology.
2. Align frontend API contracts with chapter-content naming.

### Phase 4: UI integration
1. Add source work discovery and selection UI.
2. Add source work scoped novel browsing.
3. Optionally add cross-novel chapter-next navigation.

## Open Decisions

1. Should source work metadata edits be admin-only in V1, or user-scoped with explicit source-work roles?
2. Should `GET /source-works/{id}` return empty child list when none visible, or return 404?
3. What exact authority is required for novel attach/detach (owner only vs owner or editor)?

## Relevant Files

- `backend/src/novels/models.py` - Novel/chapter/chapter-content schema and constraints.
- `backend/src/novels/permissions.py` - Canonical novel visibility and contributor permission helpers.
- `backend/src/novels/service.py` - Novel/chapter/chapter-content query and mutation patterns.
- `backend/src/labels/permissions.py` - Label access model coupled to novel/chapter-content visibility.
- `backend/src/autolabels/service.py` - AutoLabel query and insert behavior scoped by novel/chapter-content access.
- `frontend/src/pages/NovelWorkspacePage.tsx` - Workspace navigation and revision selection behavior.
- `frontend/src/api/autolabels.ts` - AutoLabel request filters and request shape.
- `docs/architecture.md` - High-level architecture and service responsibilities.
- `docs/permissions.md` - Permission conventions and zero-knowledge behavior.
- `docs/editable-with-labels.md` - Text versioning and concurrency rationale.
- `docs/workspace-implementation.md` - Workspace data flow and UX context.

## See Also

- [architecture.md](architecture.md) - Core service boundaries and communication patterns.
- [permissions.md](permissions.md) - Existing permission helper architecture and privacy posture.
- [database-schema.md](database-schema.md) - Current relational model details.
- [editable-with-labels.md](editable-with-labels.md) - Why text versioning remains important.
- [api-design.md](api-design.md) - Endpoint naming and request/response conventions.