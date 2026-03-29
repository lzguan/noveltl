# Workspace Implementation

**Last Updated**: March 28, 2026
**Status**: Complete

This document explains how the `NovelWorkspacePage` and its child components are built. It covers the component architecture, React patterns used, data flow, and how the pieces connect to the backend API. If you are new to React or want to understand the workspace internals, start here.

---

## Table of Contents

1. [Overview](#overview)
2. [Layout](#layout)
3. [Component Tree](#component-tree)
4. [React Concepts Used](#react-concepts-used)
5. [State Organization](#state-organization)
6. [Data Flow: How Everything Loads](#data-flow-how-everything-loads)
7. [Two Modes: Edit and Label](#two-modes-edit-and-label)
8. [Center Panel: Three Display Modes](#center-panel-three-display-modes)
9. [Label Rendering Pipeline](#label-rendering-pipeline)
10. [Optimistic Label Editing](#optimistic-label-editing)
11. [Inline Text Editing](#inline-text-editing)
12. [NER Integration](#ner-integration)
13. [URL Sync](#url-sync)
14. [Revision Cache](#revision-cache)
15. [Known Limitations](#known-limitations)

---

## Overview

The workspace is a single-page tool at `/workspace/:novel_id` where users annotate novel chapters with named entity labels, run NER models, and edit text. It replaces the old editor page and is the primary interface for all annotation work.

The workspace is a single large component (`NovelWorkspacePage`) that owns all state and passes slices of it to child components via props. This is sometimes called a "smart parent / dumb children" pattern — the children are mostly presentational and call callbacks to communicate upward.

## Layout

```
+------------------------------------------------------+
|  SelectorsBar (chapter, revision, mode toggle)       |
+----------------------------+-------------------------+
|                            | Top tabs: [Novel]       |
|   Center panel             | Mode tabs: [Labels|NER] |
|   (text display or editor) |                         |
|                            | Right panel content     |
|                            | (varies by active tab)  |
+----------------------------+-------------------------+
```

- **SelectorsBar** (top): chapter dropdown, revision dropdown, edit/label mode toggle
- **Center panel** (left): chapter text — read-only, annotated with labels, or editable textarea
- **Right panel** (right, 380px): tabbed sidebar with Novel metadata, editor controls, labels list, NER controls, filters

## Component Tree

```
NovelWorkspacePage
  SelectorsBar           — dropdowns for chapter/revision, mode toggle
  InlineTextEditor       — textarea for editing (edit mode only)
  AnnotatedText          — text with colored label highlights (label mode)
  ChapterTextViewer      — plain text display (fallback)
  LabelPopover           — popup when clicking an existing label
  NewLabelPopover        — popup when selecting text to create a label
  RightPanel             — tabbed container for the right sidebar
    LabelsPanel          — label list with sort/filter/search
    NerPanel             — NER run controls, preview, load into group
    LabelGroupSelector   — dropdown to pick a label group (used in multiple tabs)
```

## React Concepts Used

This section explains the React hooks and patterns used in the workspace, from basics to more advanced usage.

### `useState` — Local State

```tsx
const [novel, setNovel] = useState<Novel | null>(null);
```

`useState` creates a piece of state and a function to update it. When you call `setNovel(newValue)`, React re-renders the component with the new value. The generic `<Novel | null>` tells TypeScript what types the state can hold.

The workspace has ~30 state variables. Each `set*` function triggers a re-render when called with a new value.

### `useEffect` — Side Effects

```tsx
useEffect(() => {
    if (!novel_id) return;
    // fetch data...
}, [novel_id]);
```

`useEffect` runs code **after** the component renders. The array at the end (`[novel_id]`) is the **dependency array** — the effect only re-runs when those values change. This is how the workspace triggers API calls when selections change:

- `[novel_id]` — fetch novel, chapters, label groups on mount
- `[selectedChapterId]` — fetch revisions when chapter changes
- `[selectedRevisionId]` — fetch revision text when revision changes
- `[labelsTabGroupId, revisionTextId]` — fetch labels when group or text changes

Without the dependency array, the effect would run on every render (bad). With `[]`, it runs once on mount. With `[x]`, it runs when `x` changes.

### `useCallback` — Stable Function References

```tsx
const handleRevisionChange = useCallback((revisionId: string | null) => {
    setSelectedRevisionId(revisionId);
    // ...
}, [selectedChapterId]);
```

Functions defined inside a component are recreated every render. `useCallback` memoizes the function so it only changes when its dependencies change. This matters when passing functions as props — without `useCallback`, child components would re-render every time even if nothing meaningful changed.

The dependency array works the same as `useEffect`: the function is recreated only when listed dependencies change.

### `useMemo` — Derived/Computed Values

```tsx
const nextChapterNum = useMemo(() => {
    if (chapters.length === 0) return 1;
    return Math.max(...chapters.map((c) => c.chapterNum)) + 1;
}, [chapters]);
```

`useMemo` caches a computed value so it is only recalculated when dependencies change. Used for:

- `nextChapterNum` — derived from chapters list
- `filteredAutoLabelMetas` — auto-label metas filtered to current revision text
- `autoLabelMeta` — the currently selected auto-label from the filtered list
- `knownEntityGroups` — unique entity groups extracted from labels
- `sources` — the label rendering configuration (most complex memo)

### `useRef` — Values That Don't Trigger Re-renders

```tsx
const textContainerRef = useRef<HTMLDivElement>(null);
const revisionCacheRef = useRef<Map<string, string>>(new Map());
```

`useRef` stores a value that persists across renders but **does not trigger re-renders** when changed. Two uses in the workspace:

1. **DOM reference** (`textContainerRef`): attached to a div via `ref={textContainerRef}` so we can call `container.querySelector(...)` to scroll to labels
2. **Mutable cache** (`revisionCacheRef`): maps `chapterId -> revisionId` to remember which revision was last viewed per chapter. Using `useState` here would cause unnecessary re-renders.

### Props and Callbacks — Parent-Child Communication

Children communicate with the parent through **props** (data flowing down) and **callbacks** (events flowing up):

```tsx
// Parent passes data down and a callback up
<SelectorsBar
    chapters={chapters}                    // data down
    selectedChapterId={selectedChapterId}  // data down
    onChapterChange={handleChapterChange}  // callback up
/>

// Child calls the callback when something happens
const SelectorsBar = ({ chapters, selectedChapterId, onChapterChange }) => (
    <select onChange={(e) => onChapterChange(e.target.value)}>
        {chapters.map(ch => <option key={ch.chapterId} value={ch.chapterId}>...</option>)}
    </select>
);
```

This is one-way data flow: the parent owns the state, children request changes via callbacks, and the parent decides what to do.

## State Organization

The workspace state is grouped by concern:

| Group | Variables | Purpose |
|-------|-----------|---------|
| Core data | `novel`, `chapters`, `labelGroups` | Fetched once on mount |
| Selection | `selectedChapterId`, `chapterRevisions`, `selectedRevisionId`, `revisionText`, `revisionTextId` | What the user is looking at |
| Labels tab | `labelsTabGroupId`, `labelsTabLabelData`, `labelsTabLabels` | Labels panel state |
| NER tab | `nerTabGroupId`, `nerTabLabels`, `autoLabelMetas`, `selectedAutoLabelId`, etc. | NER panel state |
| Filters tab | `filtersTabGroupId` | Filters panel state (deferred) |
| Popovers | `activePopover`, `pendingOpError` | Label editing popups |
| Right panel | `activeRightPanel`, `scoreThreshold`, `entityGroupFilter`, `sortBy`, `searchWord` | Display settings |
| Novel form | `novelTitle`, `novelDescription`, etc. | Novel metadata editing |
| Editor | `newChapterNum`, `newRevisionTitle` | Chapter/revision creation |
| Loading | `loading`, `textLoading`, `error` | UI loading states |

## Data Flow: How Everything Loads

The workspace follows a **cascading fetch** pattern. Each selection triggers the next level of data loading:

```
novel_id (from URL)
  -> fetch novel, chapters, labelGroups (parallel, on mount)

selectedChapterId (user picks chapter)
  -> fetch revisions for that chapter
  -> auto-select: cached revision > primary > latest

selectedRevisionId (auto-selected or user picks)
  -> fetch revision text (content + revisionTextId)
  -> fetch auto-label metas for this revision

revisionTextId (from fetched text)
  -> fetch labels for labelsTab group + this revisionTextId
  -> fetch labels for nerTab group + this revisionTextId
  -> filter autoLabelMetas to this revisionTextId
```

Each arrow is a `useEffect` that watches the dependency and fires the next fetch. This creates a chain: changing the chapter cascades through revision selection, text loading, and label loading automatically.

## Two Modes: Edit and Label

The workspace has two modes, toggled via the SelectorsBar:

**Label mode** (default):
- Center panel shows text with colored label highlights (`AnnotatedText`)
- Clicking a label opens `LabelPopover` to edit/delete it
- Selecting text opens `NewLabelPopover` to create a label
- Right panel tabs: Labels, NER, Filters

**Edit mode**:
- Center panel shows an editable textarea (`InlineTextEditor`)
- Label interactions are disabled
- Right panel tabs: Editor (chapter/revision management), Labels (read-only)

The mode determines which tabs appear and which center panel component renders. The `handleModeChange` callback switches the active right panel tab when the mode changes.

## Center Panel: Three Display Modes

The center panel uses a conditional rendering chain:

```tsx
{workspaceMode === "edit" && revisionText && selectedRevisionId && revisionTextId ? (
    <InlineTextEditor ... />      // Edit mode: editable textarea
) : showAnnotated ? (
    <AnnotatedText ... />          // Label mode with labels: highlighted text
) : (
    <ChapterTextViewer ... />      // Fallback: plain read-only text
)}
```

- `InlineTextEditor` — renders when in edit mode with text loaded
- `AnnotatedText` — renders when labels or label groups are active
- `ChapterTextViewer` — renders when no labels are selected (or text is null/loading)

## Label Rendering Pipeline

Labels from multiple sources (labels tab, NER tab, NER preview) are combined into a unified rendering model. This is the most complex part of the workspace.

### Step 1: Build `sources` array (`useMemo`)

The `sources` memo assembles a `LabelSourceConfig[]` — each entry describes a set of labels with styling info:

```ts
{
    sourceKey: "labelsTab",          // unique identifier
    labels: labelsTabLabels,         // the label array
    style: "bright" | "dim",        // visual prominence
    mode: "highlight" | "underline", // render style
    interactive: true | false,       // can user click these?
    priority: 0,                     // lower = rendered on top
}
```

Which sources are included depends on the active right panel tab. The labels tab's labels are "bright" when that tab is active, "dim" when another tab is active, and vice versa.

### Step 2: Segment text (`buildMultiSourceSegments` in `labelOps.ts`)

This function takes the raw text and all label sources and splits the text into segments at every label boundary. Each segment knows which labels overlap it and from which source. This handles overlapping labels from different sources.

### Step 3: Style each segment (`resolveSegmentStyle` in `labelOps.ts`)

For each segment, determines the CSS: background color for highlights, border for underlines, cursor style for interactive labels.

### Step 4: Render in `AnnotatedText`

Each segment becomes a `<span>` with the computed styles, data attributes for character positions, and click handlers for interactive labels.

## Optimistic Label Editing

When a user adds, edits, or deletes a label, the workspace uses **optimistic updates**:

1. Apply the change locally immediately (`applyOpToLabels`)
2. Send the change to the server (`updateLabelDataStream`)
3. If the server call fails, **revert** to the snapshot taken before step 1

```tsx
const handleLabelOp = useCallback(async (op: LabelOp) => {
    const ld = await ensureLabelData();     // create LabelData if needed
    const snapshot = labelsTabLabels;        // save current state
    setLabelsTabLabels(prev => applyOpToLabels(prev, op));  // optimistic update
    try {
        await updateLabelDataStream(ld.labelDataId, { ops: [op] });
    } catch {
        setLabelsTabLabels(snapshot);        // revert on failure
    }
}, [ensureLabelData, labelsTabLabels]);
```

This pattern makes the UI feel instant — the user sees the change immediately without waiting for the network round trip.

## Inline Text Editing

When in edit mode, `InlineTextEditor` provides a textarea for modifying revision text:

1. User edits text in the textarea
2. User clicks **Save**
3. `diffToTextOps(oldText, newText)` computes minimal `TextOp[]` using `diff-match-patch-es`
4. Sends ops to `PATCH /revisions/{id}/text` with `revisionTextId` for optimistic concurrency
5. On success: re-fetches text to get the new `revisionTextId`, reloads labels (backend shifts label positions automatically)
6. On 409 Conflict: text was modified elsewhere — refreshes and shows error

The diff library produces minimal character-level diffs, which is important because the backend **drops labels that straddle edit boundaries**. Smaller diffs preserve more labels.

### Optimistic Concurrency

Every revision text has a UUID (`revisionTextId`) and a version number. When you save:
- You send the `revisionTextId` you were editing against
- The backend checks it matches the current latest version
- If someone else edited first, you get a 409 — your `revisionTextId` is stale
- You must refresh and retry

This prevents two users from silently overwriting each other's edits.

## NER Integration

The NER panel lets users run Named Entity Recognition on the current revision text:

1. **Run NER**: sends model name + params to `POST /auto-labels/`, which enqueues a background worker job
2. **Poll**: while status is `pending` or `processing`, polls every 3 seconds for updates
3. **Preview**: once `done`, user can toggle a preview overlay showing raw NER results on the text
4. **Load into group**: copies NER results into a label group as real labels

The auto-label metas are filtered to the current `revisionTextId` so the dropdown only shows runs relevant to the text version being viewed.

## URL Sync

The workspace syncs key selection state to URL query parameters:

```
/workspace/abc-123?chapter=ch-456&revision=rev-789&labelsGroup=lg-012&nerGroup=ng-345
```

A `useEffect` writes state to the URL whenever selections change (using `setSearchParams` with `replace: true` to avoid polluting browser history). On mount, another function reads the URL params back into state.

This means bookmarking or sharing a workspace URL preserves the user's exact view.

## Revision Cache

A `useRef<Map<string, string>>` maps `chapterId` to the last-selected `revisionId`. When switching chapters:

1. Fetch revisions for the new chapter
2. Check the cache for a previously selected revision
3. If found and still exists in the revision list, restore it
4. Otherwise fall back to primary revision, then latest

The cache is cleared for a chapter when its cached revision is deleted. Using `useRef` instead of `useState` avoids unnecessary re-renders when the cache updates.

## Known Limitations

- **No unsaved changes warning**: switching from edit mode with unsaved text changes silently discards them
- **No drag-to-resize labels**: label boundary adjustment via dragging is not yet implemented (phase 7 of the incremental plan in [ui-requirements.md](ui-requirements.md))
- **Filters panel is deferred**: shows a placeholder, not yet functional
- **No undo/redo** for label or text operations
- **No real-time collaboration**: two users editing simultaneously will hit 409 conflicts
- **Large chapter text**: no virtualization — very long chapters may cause performance issues in `AnnotatedText`

## Relevant Files

- `frontend/src/pages/NovelWorkspacePage.tsx` — Main workspace component, owns all state
- `frontend/src/components/workspace/SelectorsBar.tsx` — Chapter/revision dropdowns, mode toggle
- `frontend/src/components/workspace/AnnotatedText.tsx` — Label-highlighted text display
- `frontend/src/components/workspace/ChapterTextViewer.tsx` — Plain text display fallback
- `frontend/src/components/workspace/InlineTextEditor.tsx` — Textarea editor with save/discard
- `frontend/src/components/workspace/diffToTextOps.ts` — Diff-to-TextOps conversion utility
- `frontend/src/components/workspace/labelOps.ts` — Label segmentation, multi-source rendering logic
- `frontend/src/components/workspace/RightPanel.tsx` — Tabbed sidebar container
- `frontend/src/components/workspace/LabelsPanel.tsx` — Label list with sort/filter/search
- `frontend/src/components/workspace/NerPanel.tsx` — NER run controls and preview
- `frontend/src/components/workspace/LabelPopover.tsx` — Edit/delete label popup
- `frontend/src/components/workspace/NewLabelPopover.tsx` — Create new label popup
- `frontend/src/components/workspace/LabelGroupSelector.tsx` — Label group dropdown
- `frontend/src/api/novels.ts` — Novel/chapter/revision API functions
- `frontend/src/api/labels.ts` — Label data API functions
- `frontend/src/api/autolabels.ts` — AutoLabel API functions
- `frontend/src/types/novel.ts` — Core type definitions (Revision, RevisionText, TextOp, etc.)
- `frontend/src/types/label.ts` — Label type definitions

## See Also

- [ui-requirements.md](ui-requirements.md) — Original spec for workspace UI, incremental implementation phases
- [editable-with-labels.md](editable-with-labels.md) — Design doc for text editing with label preservation
- [architecture.md](architecture.md) — Overall system architecture
- [frontend-testing.md](frontend-testing.md) — Frontend testing standards
- [filter-system.md](filter-system.md) — Filter pipeline (deferred in workspace)
- [background-jobs.md](background-jobs.md) — AutoLabel worker system
