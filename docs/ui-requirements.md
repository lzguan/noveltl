# UI Requirements — Annotation Workspace

**Last Updated**: 2026-03-17    
**Status**: Approved

This document specifies the `NovelWorkspace` component — the primary annotation interface for NovelTL. It is the most complex component in the codebase and should be implemented incrementally.

---

## Table of Contents

1. [Purpose](#purpose)
2. [Route](#route)
3. [Layout (single instance)](#layout-single-instance)
4. [Selectors Bar](#selectors-bar)
5. [Chapter Text Viewer](#chapter-text-viewer)
6. [Labels Panel](#labels-panel-right-sidebar-default-tab)
7. [NER Panel](#ner-panel-right-sidebar-ner-tab)
8. [Filters Panel](#filters-panel-right-sidebar-filters-tab)
9. [State Model](#state-model)
10. [Incremental Implementation Order](#incremental-implementation-order)
11. [What This Document Does NOT Cover (yet)](#what-this-document-does-not-cover-yet)
12. [Relevant Files](#relevant-files)
13. [See Also](#see-also)

---

## Purpose

An Overleaf-style annotation workspace where a user can:

1. Load a novel, navigate chapters, and select a revision
2. View the chapter text with NER labels rendered as inline coloured highlights
3. Edit labels manually — add by selecting text, update entity group or drag span boundaries, delete
4. Trigger autolabelling (NER) on a revision, preview raw results, and promote them into a label group
5. Run filters on label data to bulk-approve or bulk-reject low-quality labels

The manage-novels section (`/edit/novels`) handles content management (uploading revisions, etc.). This workspace is for annotation and review.

---

## Route

```
/workspace/:novel_id
```

The novel is fixed at route level. Chapter, revision, and label group are selected within the page. A `?chapter=N&revision=R&group=G` query string is kept in sync so users can bookmark or share a specific view.

> **Note on NER constraint:** The autolabel system only processes revisions where `is_final = true`. A revision must be finalized before NER can run on it.

---

## Layout (single instance)

```
┌─────────────────────────────────────────────────────────────────────┐
│ Navbar                                                              │
├─────────────────────────────────────────────────────────────────────┤
│  Novel: My Novel   Chapter: [Ch 1 ▼]  Revision: [Draft v2 ▼]        │
│  Label Group: [NER Run 1 ▼]  [+ New Group]      [Run NER ▼]         │
├──────────────────────────────────────┬──────────────────────────────┤
│                                      │  [Labels] [NER] [Filters]    │
│  Chapter text with inline            ├──────────────────────────────┤
│  highlighted spans…                  │                              │
│                                      │  (active panel content)      │
│  他来自[北京]₍LOC₎，是一名            │                               │
│  [程序员]₍PER?₎。[刘备]₍PER₎说…       │                              │
│                                      │                              │
│  (scrollable)                        │  (scrollable)                │
└──────────────────────────────────────┴──────────────────────────────┘
```

Right panel is tabbed: **Labels** | **NER** | **Filters**. Default tab: Labels.

---

## Selectors Bar

### Novel
Fixed from the route param. Display the novel title as read-only text.

### Chapter
Dropdown of all chapters for the novel, sorted by `rawChapterNum`. Switching chapter resets revision selection, label data, and autolabel state.

### Revision
Dropdown of revisions for the selected chapter. Default: the primary revision (if one exists), otherwise the most recent. Only `rawChapterRevisionTitle` is shown; the revision ID drives all subsequent data loading.

### Label Group
Dropdown of all `LabelGroup` records for the novel. Switching label group reloads the label data for the current revision. A **"+ New Group"** button opens a small inline form (name only — reuse `createLabelGroup`). If no `LabelData` exists for the selected `(labelGroupId, revisionId)` pair yet, the labels panel is empty with a prompt to run NER or add labels manually.

> **Data model reminder:** `LabelGroup` → `LabelData` (one per revision per group) → `Label[]`. A `LabelData` is created explicitly via `POST /label-groups/{id}/label-datas` before any ops can be sent.

---

## Chapter Text Viewer

### Rendering labels as spans

The chapter text is a plain string (`rawChapterRevisionText`). Labels carry `labelStart` and `labelEnd` character offsets into that string.

> **Implementation decision:** Custom `<AnnotatedText>` component — no external annotation library. Splits `text` into plain runs and labelled spans based on character offsets, with draggable handles for resize. UTF-8 is safe for CJK content via standard JavaScript string slicing (Chinese/Japanese/Korean characters are BMP code points, single UTF-16 code units).

**Span algorithm:**

```
1. Sort labels by labelStart ascending.
2. Walk the text building a flat segment list:
   - text run (plain string)
   - label span (start, end, labelId, entityGroup, score, dirty)
3. Overlapping labels: render outer label as span, overlap region as nested span.
   Flag as a known edge case — keep simple for now.
```

Each entity group gets a consistent colour from a fixed palette keyed by entity group string
(`PER` → blue, `LOC` → green, `ORG` → orange, unknown → grey).

**Visual states:**
- `labelDirty = true` → subtle dot/underline indicator ("manually edited / unverified")
- `labelScore < scoreThreshold` → dimmed/greyed out (threshold set in Labels panel; default 0 = show all)
- Active (currently hovered or selected in sidebar) → brightened border

### Label editing: drag to resize / move

Rather than clicking to get a popover for position changes, the user should be able to drag span boundaries directly in the text:

- **Drag start handle** → adjusts `labelStart`
- **Drag end handle** → adjusts `labelEnd`
- **Drag span body** → moves the entire span (adjusts both start and end)

**Snapping:** Drags should snap to word boundaries. Needs a word-boundary algorithm that works for CJK text (can't split on whitespace only — consider using `Intl.Segmenter` with `granularity: 'word'`).

**Cursor:** Custom cursor during drag (resize cursor on handles, grab cursor on body).

> **Implementation note:** This is the hardest single interaction in the workspace. It may need to be deferred to a later milestone after basic click-to-edit works. The data contract is clear: emit an `UpdateLabelOp` with `new_start_pos` / `new_end_pos` and derive the new word from `text.slice(new_start_pos, new_end_pos)`.

### Text selection → new label

When the user selects text in the viewer (`mouseup` event on the text container):

1. Read `window.getSelection()` to get the selected range.
2. Map the DOM selection back to character offsets in the raw string. Requires tracking which DOM node covers which character range.
3. Show a **creation popover** anchored near the selection with:
   - Selected text shown as read-only (the `word` is the slice, not user-editable)
   - Entity group: free-text input with datalist suggestions drawn from distinct entity groups in current label data
   - Confirm / Cancel
4. On confirm:
   - If no `LabelData` exists yet for this (revision, labelGroup): create one first via `POST /label-groups/{id}/label-datas`
   - Then send `PATCH /label-datas/{id}` with `[AddLabelOp]`
5. Apply optimistically to local state, reconcile on server response.

### Click existing label → edit popover

Clicking a labelled span opens a small inline popover (not a modal — dismisses on outside click or Escape):

- **Entity group:** free-text input with datalist of existing groups — this is the main editable field
- **Word:** read-only, showing `text.slice(labelStart, labelEnd)` — word is fully determined by position
- **Dirty flag:** checkbox ("Mark as manually verified" — note: `dirty = true` means unverified/modified by hand; `false` means clean NER output)
- **Save** → emit `UpdateLabelOp` with new `entity_group`, `dirty`, and derived `word` from current positions
- **Delete** → emit `DeleteLabelOp`, close popover
- **Cancel** → close without changes

The popover is an absolutely-positioned div rendered via React portal (same pattern as `Modal`).

### Optimistic updates

Apply ops to local `labels` state immediately without waiting for the server round-trip, then reconcile with the server response:

```typescript
// Snapshot for rollback
const snapshot = [...labels]

// 1. Apply locally
setLabels(applyOpToLabels(labels, op))
setPendingOp(true)

// 2. Send to server
try {
    await updateLabelDataStream(labelDataId, [op])
    // PATCH returns 204 — trust local state; no re-fetch needed
} catch {
    // Roll back
    setLabels(snapshot)
    setPendingOpError('Failed to save — change rolled back')
} finally {
    setPendingOp(false)
}
```

`applyOpToLabels(labels, op)` is a pure function implementing the same logic as the server:
- `add`: append new label
- `delete`: remove label matching `start_pos`, `end_pos`, `word`
- `update`: find label by `start_pos`/`end_pos`/`word`, replace fields

> **Future:** Server-side session UUID locking (client gets a session UUID on chapter navigation; stale writes rejected) is a planned enhancement. Defer until the basic optimistic approach causes problems.

---

## Labels Panel (right sidebar, default tab)

A scrollable list of all labels for the current revision + label group.

**Columns:** Word · Entity Group · Score · Position (char offset)

**Controls:**
- Sort by: position (default) | entity group | score | word
- Filter by entity group: multi-select chips (one chip per distinct entity group in current labels)
- Score threshold slider: dim labels below this score (does not hide — labels are still visible in the text but greyed out). Range 0–1, default 0.
- Search by word: text input

**Row interactions:**
- Click row → scroll chapter viewer to that span and briefly highlight it ("flash" the span)
- Click entity group chip in row → open edit popover for that label

**Counter:** "42 labels · 3 below threshold"

---

## NER Panel (right sidebar, NER tab)

Displays autolabel status for the current revision and allows triggering NER.

> **Constraint reminder:** NER only runs on finalized (`is_final = true`) revisions. If the current revision is not finalized, show a warning instead of the Run NER button.

> **Deduplication constraint:** The backend has a unique constraint on `(revision_id, model_name, model_params)`. Running NER twice with identical params returns `200 []` silently — no new autolabel is created. "Re-run NER" must change params slightly (e.g. bump a param) or the backend needs a retry endpoint (not yet implemented). Surface this constraint in the UI — disable "Re-run" if params have not changed and the existing run succeeded.

**Status display:**
- No autolabel for this revision → "No NER has been run for this revision."
- `pending` → spinner + "Queued..."
- `processing` → spinner + "Running NER..."
- `done` → "✓ NER complete · model: cluener"
- `failed` → "✗ NER failed" + `autoLabelMessage`

**Run NER form:**
- Model name: text input (default `'cluener'`)
- Model params: collapsible JSON textarea (default `{}`)
- **Run NER** button

**Viewing results without creating a LabelData ("preview mode"):**

After NER completes (`done`), the user can preview raw autolabel results in the text viewer without committing them to a label group. This overlays the autolabel spans in a distinct visual style (e.g. dashed border, lighter opacity) separate from the active label group's highlights. Toggle via a "Preview NER results" checkbox in the NER panel.

This requires fetching the full `AutoLabel` (with `auto_label_data`) via `GET /auto-labels/{auto_label_id}` when preview is enabled. The preview renders read-only — no editing, no ops.

**Load results into label group:**

Once satisfied with the NER output, the user can promote it into the current label group:

```
POST /label-groups/{labelGroupId}/label-datas/auto-labels
{
    "model_name": "cluener",
    "model_params": {},
    "raw_chapter_revision_ids": [currentRevisionId]
}
```

Returns `CreateLabelDataByAutoLabelStatus`:
- `success`: list of revision IDs that were imported
- `errors`: list of `[revisionId, errorMessage]` tuples

Show a summary: "Imported N labels. X revisions failed." On success, reload label data and exit preview mode.

Polling: 3s interval while status is `pending` or `processing`.

---

## Filters Panel (right sidebar, Filters tab)

> **DEFERRED.** Implement last. The full spec is preserved below for reference but do not implement this until all other panels are working.

Allows running filters from the `filters` API on the current label group.

**Step 1 — Select filter**
Dropdown populated from `GET /filters/schemas` → `Record<string, SchemaInfo>`.

**Step 2 — Configure options**
Render a dynamic form from the `flagInstancesOptionsSchema` JSON Schema field. Minimal recursive renderer:

```
number / integer  → <input type="number" min/max from schema>
string            → enum present? <select> : <input type="text">
boolean           → <input type="checkbox">
array             → list of items with +/- row buttons
unknown type      → raw JSON textarea fallback + console.warn
```

**Step 3 — Flag instances**
"Run Filter" → `POST /filters/{filter_name}/flag-instances` with options. Returns list of instances.

**Step 4 — Group and review**
Group flagged instances by word. Per group: show word, count, entity group, context snippets (via `POST /filters/{filter_name}/get-contexts`). Per-group Approve / Reject.

**Step 5 — Apply**
"Apply" → `POST /filters/{filter_name}/apply` with approved instances and `label-group-id`. Reload label data.

---

## State Model

```typescript
// ── Route / navigation ──────────────────────────────────────────────
novelId: number                               // from route param (:novel_id)

// ── Novel-level data ─────────────────────────────────────────────────
novel: Novel | null                           // fetched on mount
chapters: RawChapter[]                        // all chapters, sorted by rawChapterNum
labelGroups: LabelGroup[]                     // all label groups for this novel

// ── Chapter selection ─────────────────────────────────────────────────
selectedChapterId: number | null              // drives revision list + URL sync
chapterRevisions: RawChapterRevisionMeta[]    // revisions for selected chapter

// ── Revision selection ────────────────────────────────────────────────
selectedRevisionId: number | null             // drives text + labelData + autoLabel
revisionText: string | null                   // rawChapterRevisionText, fetched on change
textContainerRef: React.RefObject<HTMLDivElement>  // DOM ref for offset mapping

// ── Label group selection ─────────────────────────────────────────────
selectedLabelGroupId: number | null

// ── Label data (active annotation layer) ─────────────────────────────
labelData: LabelData | null                   // null = no LabelData exists yet
labels: Label[]                               // local mutable copy, updated optimistically
pendingOp: boolean                            // true while PATCH is in-flight
pendingOpError: string | null                 // shown inline, cleared on next op

// ── Label interaction state ───────────────────────────────────────────
activePopover:
    | { type: 'new'; start: number; end: number; anchorRect: DOMRect }
    | { type: 'edit'; label: Label; anchorRect: DOMRect }
    | null
dragState:
    | { labelId: number; handle: 'start' | 'end' | 'body'; originX: number; originStart: number; originEnd: number }
    | null
highlightedLabelId: number | null             // label scroll-to'd from sidebar (flash animation)

// ── Label display settings ─────────────────────────────────────────────
scoreThreshold: number                        // 0–1, labels below this are dimmed
entityGroupFilter: Set<string>                // empty = show all groups
sortBy: 'position' | 'score' | 'entityGroup' | 'word'
searchWord: string

// ── NER (autolabel) state ──────────────────────────────────────────────
autoLabelMeta: AutoLabelMeta | null           // for current revision (polled)
autoLabelPreview: AutoLabel | null            // full AutoLabel with label data (preview mode)
showAutoLabelPreview: boolean                 // overlay raw NER results on text
nerModelName: string                          // default 'cluener'
nerModelParams: Record<string, unknown>       // default {}

// ── Right panel ────────────────────────────────────────────────────────
activeRightPanel: 'labels' | 'ner' | 'filters'

// ── Filters panel (deferred) ───────────────────────────────────────────
// filterState: FilterWorkflowState            // spec TBD

// ── Global loading / error ─────────────────────────────────────────────
loading: boolean                              // initial data fetch
error: string | null                          // fatal load error
```

### Derived values (computed, not stored)

```typescript
// Entity groups seen in current labels (for datalist suggestions)
const knownEntityGroups: string[] = useMemo(
    () => [...new Set(labels.map(l => l.labelEntityGroup))].sort(),
    [labels]
)

// Filtered + sorted label list for the sidebar
const visibleLabels: Label[] = useMemo(
    () => labels
        .filter(l => entityGroupFilter.size === 0 || entityGroupFilter.has(l.labelEntityGroup))
        .filter(l => !searchWord || l.labelWord.includes(searchWord))
        .sort(sortComparators[sortBy]),
    [labels, entityGroupFilter, searchWord, sortBy]
)

// Current revision is finalized (required for NER)
const canRunNer: boolean = useMemo(
    () => chapterRevisions.find(r => r.rawChapterRevisionId === selectedRevisionId)
              ?.rawChapterRevisionIsFinal ?? false,
    [chapterRevisions, selectedRevisionId]
)
```

### URL sync

Keep `?chapter=`, `?revision=`, and `?group=` in sync using `useSearchParams` from React Router.
On initial mount, read query params to restore state (e.g. from a bookmarked URL).

---

## Incremental Implementation Order

Build and test in this order. Each step is independently usable:

1. **Selectors + plain text display** — fetch revision text and display as plain text. Chapter/revision/group dropdowns work. URL query sync works.
2. **Read-only label highlighting** — fetch label data, render spans with entity group colours. No editing yet.
3. **Click-to-edit popover** — update entity group and delete existing labels. No drag yet.
4. **Text selection → new label** — add label creation. Requires DOM offset mapping.
5. **Labels panel** — scrollable list with sort/filter/search, scroll-to-label flash.
6. **NER panel** — trigger autolabel, poll status, preview mode, load into label group.
7. **Drag-to-resize spans** — the hardest interaction. Implement after everything else works.
8. **Filters panel** — deferred; implement last.

---

## What This Document Does NOT Cover (yet)

- **Side-by-side dual view**: deferred. Requires optional route query params `?novel2=`, `?chapter2=`, `?revision2=`, `?group2=` and a two-column layout variant. Architecture should support it (component takes explicit IDs as props), but multi-instance state sync is a separate spec.
- **Glossary panel**: no backend support exists yet.
- **Real-time collaboration**: no WebSocket support. Not in scope.
- **Mobile / responsive**: not a priority.
- **Undo/redo**: the immutable revision model makes undo non-trivial (requires inverse ops). Deferred.

---

## Relevant Files

- `frontend/src/api/labels.ts` - Label data CRUD + `updateLabelDataStream` (PATCH returns 204)
- `frontend/src/api/autolabels.ts` - AutoLabel trigger + status polling
- `frontend/src/api/novels.ts` - Chapter/revision fetching
- `frontend/src/types/novel.ts` - `RawChapter`, `RawChapterRevisionMeta`
- `frontend/src/types/label.ts` - `Label`, `LabelData`, `LabelGroup`, `LabelOp`
- `frontend/src/types/autolabel.ts` - `AutoLabel`, `AutoLabelMeta`, `AutoLabelProgress`
- `frontend/src/components/common/Modal.tsx` - Portal pattern reference for popover

## See Also

- [architecture.md](architecture.md) - System overview
- [background-jobs.md](background-jobs.md) - AutoLabel state machine, NER constraints
- [api-design.md](api-design.md) - REST patterns (PATCH, POST action endpoints)
- [conventions.md](conventions.md) - Frontend naming, component structure