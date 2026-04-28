# Labeled Text Library Implementation

**Last Updated**: April 26, 2026  
**Status**: Draft

This document describes the current implementation of the frontend labeled text library in `frontend/src/components/labeled-text-lib/`. It explains the actual data model, segmentation rules, mutation model, and React adapters that exist today. Read this before changing `EditNovelPage` or drafting higher-level editor architecture.

---

## Table of Contents

1. [Overview](#overview)
2. [Scope](#scope)
3. [Core Data Model](#core-data-model)
4. [Segmentation](#segmentation)
5. [Segment Manager](#segment-manager)
6. [React Adapters](#react-adapters)
7. [Rendering Helpers](#rendering-helpers)
8. [What The Library Does Not Own](#what-the-library-does-not-own)
9. [How NovelTL Should Use It](#how-noveltl-should-use-it)
10. [Known Limitations](#known-limitations)
11. [Relevant Files](#relevant-files)
12. [See Also](#see-also)

---

## Overview

The labeled text library is a small frontend subsystem for rendering text with interval annotations and, in the dynamic case, mutating the text/annotation model while preserving rendering invariants.

Today it has three layers:

1. Core types in `core/types.ts`
2. Segmentation and mutable document logic in `core/segmenters.ts` and `core/segmentManager.ts`
3. React adapters and renderer helpers in `react/`

The important point is that this library is not a full editor architecture. It knows how to:

- represent labels as intervals over text
- partition text into renderable segments
- maintain those segments while text/label mutations occur
- render the segments statically or from an externally owned manager

It does not know anything about chapters, label groups, backend flushing, edit modes, or queueing.

## Scope

The current implementation supports two main use cases:

1. Static rendering of a text plus labels
2. Dynamic rendering driven by an externally owned `SegmentManager`

The design is generic over:

- style type `S`
- label type `L extends StyledLabel<S>`

This means the library is intentionally not coupled to NovelTL label schemas. NovelTL-specific concerns should stay outside the library and be adapted into its generic types.

## Core Data Model

The core types live in [frontend/src/components/labeled-text-lib/core/types.ts](/workspaces/NovelTL_Dev/frontend/src/components/labeled-text-lib/core/types.ts:1).

Important concepts:

- `StyledLabel<S>`
  - A label with an absolute half-open interval `[start, end)` into the source text
  - Also carries a style payload `S`

- `Segment<S, L>`
  - A contiguous slice of text with `start`, `text`, and `labels`
  - Inside a segment, label intervals are relative to `segment.start`

- `ManagedLabel`
  - Extends a label with a stable `id`
  - Required by the mutable manager

- `ManagedSegment`
  - A segment with a stable segment `id`

The absolute-vs-relative distinction is the main thing to remember:

- external labels are stored in absolute text coordinates
- labels inside rendered segments are projected into segment-local coordinates

## Segmentation

Segmentation logic lives in [core/segmenters.ts](/workspaces/NovelTL_Dev/frontend/src/components/labeled-text-lib/core/segmenters.ts:1).

### `makeBasicSegmenter`

`makeBasicSegmenter(gap)` partitions a text into ordered segments.

Behavior:

- unlabeled regions become unlabeled segments
- overlapping labels are merged into one labeled segment
- labels inside a segment are rewritten to segment-local coordinates
- the optional `gap` parameter controls whether nearby/touching labels should be merged into the same segment

Practical `gap` meaning:

- `gap = 0`
  - touching labels may remain separate
- `gap > 0`
  - close labels can be merged into one larger segment

This matters because the manager later relies on these segmentation boundaries when inserting/deleting text around labels.

### Reducing Segmenters

The same file also defines:

- `makeReducingSegmenter`
- `makeFullReducingSegmenter`

These are style-reduction helpers, not mutable editor primitives.

They:

- partition labeled coverage more finely
- reduce multiple overlapping styles into one style per rendered subrange

Use them when you want a visual reduction of overlap, not when you need to preserve individual labels as editable objects.

## Segment Manager

The mutable manager lives in [core/segmentManager.ts](/workspaces/NovelTL_Dev/frontend/src/components/labeled-text-lib/core/segmentManager.ts:88).

### Purpose

`SegmentManager` is a mutable document model that keeps:

- the current text
- the current segments
- label identities
- subscriber notifications

It is the library's stateful core for dynamic editing.

### Public API

The main public methods are:

- `getText()`
- `getSegmentIds()`
- `getSegment(id)`
- `getSegments()`
- `subscribe(callback)`
- `addLabel(id, label)`
- `updateLabel(id, label)`
- `removeLabel(id)`
- `insertTextAt(pos, text)`
- `deleteTextAt(pos, length)`
- `batch(fn)`

### Invariants

The manager is designed to maintain these invariants:

- segments cover the full text with no gaps or overlaps
- every segment has positive length
- every label has positive length
- every label is fully contained within exactly one segment
- labels returned from segments use coordinates relative to that segment

This invariant set is the main reason the manager exists. Callers mutate the document through manager operations and the manager repairs segment structure as needed.

### Internal Representation

The current implementation maintains:

- `text`
- `bounds`
  - ordered segment ranges
- `segmentsById`
- `labelsById`
- `segmentIdsByLabelId`
- `subscribers`

This is enough to answer segment queries, map labels back to segments, and rebuild local regions after edits.

### Mutation Semantics

#### Label mutations

- `addLabel`
  - merges affected segments if needed
  - inserts the label into the resulting segment

- `removeLabel`
  - removes the label
  - may split the segment again if uncovered space is large enough relative to `gap`

- `updateLabel`
  - implemented as batched remove + add

#### Text insertion

`insertTextAt` handles several cases:

- prepend at position `0`
- append at `text.length`
- insertion into unlabeled segments
- insertion near labels within an allowed gap
- insertion that invalidates overlapping labels

Notably, insertion through the middle of existing labels is destructive to those labels in the current implementation: overlapping labels are removed before the text is inserted. This is an important behavior for higher-level editor logic to understand.

#### Text deletion

`deleteTextAt`:

- removes intersecting labels
- shifts labels that occur after the deleted range
- removes affected segments
- rebuilds the local affected region using the base segmenter

This local rebuild is the main repair mechanism after destructive text edits.

### Batching

`batch(fn)` suppresses intermediate subscriber notifications while a group of operations runs. After the batch completes, one final notification is emitted.

Use this when a higher-level action is conceptually one change but implemented as several manager operations.

## React Adapters

### `StaticLabeledText`

[react/StaticLabeledText.tsx](../frontend/src/components/labeled-text-lib/react/StaticLabeledText.tsx) is the simple rendering path.

It:

- receives raw `text`
- receives raw `labels`
- receives a segmenter
- computes segments on render
- renders them with a supplied `Renderer`

Use it for read-only rendering when you do not need a persistent mutable manager.

### `DynamicLabeledText`

[react/DynamicLabeledText.tsx](../frontend/src/components/labeled-text-lib/react/DynamicLabeledText.tsx) is the dynamic adapter.

It:

- receives an already-created `SegmentManager`
- subscribes to manager changes
- mirrors `manager.getSegments()` into React state
- renders those segments
- exposes a hidden `contentEditable` for keyboard/composition/input events
- forwards pointer, keyboard, clipboard, composition, focus, and input callbacks with access to both `manager` and `caret`

This is the right adapter for NovelTL's editor work because the page can own:

- the manager lifecycle
- caret state
- mode state
- backend synchronization state

The adapter only handles rendering and event forwarding.

## Rendering Helpers

[react/Renderer.tsx](/workspaces/NovelTL_Dev/frontend/src/components/labeled-text-lib/react/Renderer.tsx:1) provides:

- `Renderer`
- plain text rendering helpers
- overlay box rendering helpers
- DOM range measurement utilities

The important split is:

- `renderText`
  - renders the visible text for a segment
- `renderOverlay`
  - optionally renders measured overlay boxes on top of the text

`makePlainBoxRenderer` is the convenience helper currently used in the editor experiments. It renders plain text plus overlay boxes whose CSS comes from a style-to-box-style function.

The built-in reducers and color helpers under `builtin/` are convenience utilities, not core architecture.

## What The Library Does Not Own

This is the most important boundary for the editor architecture.

The library does not own:

- chapter selection
- active label group / active tab / active index
- editor mode such as `"edit"` vs `"label"`
- session buffering
- backend flush queues
- optimistic synchronization state
- NovelTL permission rules
- chapter content version / `chapterContentId` reconciliation

`SegmentManager` is a document mutation primitive, not the whole page state machine.

## How NovelTL Should Use It

For the current editing direction, the intended shape is:

1. Convert backend label data into manager labels
2. Own the manager in page-level React state or memoized lifecycle logic
3. Use `DynamicLabeledText` for rendering and event capture
4. Keep higher-level editor state outside the library

The higher-level editor should likely maintain:

- backend snapshot
- optimistic local text/label snapshot
- session buffers
- flush queue
- mode / active entry / visibility

The manager should track only the live mutable text+label surface for the currently active editing context.

## Known Limitations

- There is no built-in concept of backend synchronization.
- Text edits that overlap labels are destructive to those labels in the current manager implementation.
- The manager is mutable and imperative, so higher-level code must be disciplined about lifecycle and ownership.
- `DynamicLabeledText` depends on external caret state; caret movement logic is not provided by the library.
- The library does not currently document a stable package-style public API boundary; it is still an internal subsystem.

## Relevant Files

- `frontend/src/components/labeled-text-lib/core/types.ts` - Core interval, segment, and style types
- `frontend/src/components/labeled-text-lib/core/segmenters.ts` - Basic and reducing segmentation logic
- `frontend/src/components/labeled-text-lib/core/segmentManager.ts` - Mutable segmented document model
- `frontend/src/components/labeled-text-lib/react/StaticLabeledText.tsx` - Read-only rendering adapter
- `frontend/src/components/labeled-text-lib/react/DynamicLabeledText.tsx` - Externally managed dynamic rendering adapter
- `frontend/src/components/labeled-text-lib/react/Renderer.tsx` - Renderer and overlay helpers
- `frontend/src/components/labeled-text-lib/builtin/` - Convenience style reducers and color helpers
- `frontend/src/components/labeled-text-lib/__test__/` - Behavior tests for segmentation, manager, and React rendering

## See Also

- [labeled-text-library.md](labeled-text-library.md) - Original design/motivation doc, now deprecated
- [workspace-implementation.md](workspace-implementation.md) - Existing workspace architecture doc
- [editable-with-labels.md](editable-with-labels.md) - Broader editor/backend concurrency notes
