# Labeled Text Library

**Last Updated**: March 29, 2026    
**Status**: Draft

Design doc for a standalone labeled text rendering library. The library provides a general-purpose component for displaying text with overlapping annotations from multiple sources, where the visual appearance of overlapping regions is controlled by a user-defined algebraic structure over styles.

This doc is aimed at anyone working on the workspace frontend or considering extracting this as a standalone package.

---

## Table of Contents

1. [Motivation](#motivation)
2. [Core Abstraction: Style Monoid](#core-abstraction-style-monoid)
3. [Pipeline](#pipeline)
4. [Type Definitions](#type-definitions)
5. [Segmentation Algorithm](#segmentation-algorithm)
6. [Rendering](#rendering)
7. [Examples](#examples)
8. [Integration with NovelTL](#integration-with-noveltl)
9. [Editing Integration](#editing-integration)
10. [Future: Style Transform Step](#future-style-transform-step)
11. [Package Structure](#package-structure)
12. [Relevant Files](#relevant-files)
13. [See Also](#see-also)

---

## Motivation

NovelTL's workspace displays chapter text annotated with labels from multiple sources: user-created label groups, NER model predictions, and filtered results. The current implementation (`labelOps.ts` + `AnnotatedText.tsx`) handles this but has hardcoded style logic — colors are derived from entity groups, priority determines highlight vs underline, and the rendering strategy is baked into the component.

Problems with the current approach:

1. **Inflexible overlap handling** — when labels from different sources overlap, the highest-priority source always gets the background highlight and lower-priority sources become underlines. There's no way to blend, average, or apply a custom strategy.
2. **Tightly coupled to NovelTL types** — `LabelSourceConfig` references entity groups, NER-specific colors, and "bright"/"dim" style literals.
3. **Hard to prototype new UIs** — changing how labels render (e.g., emphasize the active tab's labels, dim everything else) requires modifying `resolveSegmentStyle` directly.

The goal is a library where the user defines *what style data looks like* and *how overlapping styles combine*, and the library handles segmentation and rendering.

---

## Core Abstraction: Style Monoid

A **monoid** is a type `S` equipped with:

- A binary operation `combine: (a: S, b: S) => S` that is associative: `combine(a, combine(b, c)) === combine(combine(a, b), c)`
- An identity element `empty: S` such that `combine(empty, x) === combine(x, empty) === x`

The library requires the user to provide a `StyleConfig<S>`:

```typescript
type StyleConfig<S> = {
  combine: (a: S, b: S) => S;
  empty: S;
};
```

The `empty` value is the style for text segments where no labels overlap (plain text). The `combine` operation defines what happens when two or more labels cover the same character range — their styles are folded together.

### Why a monoid and not a product of independent properties?

Consider a style with `color`, `opacity`, and `priority`. You might think: define a monoid for color (blend), a monoid for opacity (average), a monoid for priority (max), and take their product. This works when the dimensions are independent.

But priority breaks independence — a high-priority label might want to *override* a low-priority label's color entirely, not blend with it. The priority dimension influences how color and opacity combine. This means the combine operation needs access to the full style value, not just individual fields.

A single `combine` function over the full style type handles this naturally.

---

## Pipeline

```
Labels + Styles           User provides (Label, Style) pairs
       │
       ▼
   Segmentation           Split text at label boundaries into maximal
       │                  contiguous ranges with constant label coverage
       ▼
  Style Folding           For each segment, combine all active styles
       │                  using the monoid operation
       ▼
    Rendering             Render each segment via an injectable render
                          function: (text, combinedStyle) → JSX
```

---

## Type Definitions

```typescript
// --- Core library types ---

// A label is anything with a start and end position
type LabelSpan = {
  start: number;
  end: number;
};

// A label paired with its style
type StyledLabel<S, L extends LabelSpan = LabelSpan> = {
  label: L;
  style: S;
};

// The monoid definition
type StyleConfig<S> = {
  combine: (a: S, b: S) => S;
  empty: S;
};

// Output of the segmentation step
type StyledSegment<S, L extends LabelSpan = LabelSpan> = {
  text: string;
  start: number;
  end: number;
  style: S;
  labels: L[];  // all labels covering this segment (for click handlers, tooltips, etc.)
};

// The render function signature
type SegmentRenderer<S, L extends LabelSpan = LabelSpan> = React.FC<{
  text: string;
  style: S;
  labels: L[];
  charStart: number;
  charEnd: number;
}>;
```

---

## Segmentation Algorithm

The segmentation algorithm splits text into maximal contiguous ranges where the set of overlapping labels is constant. This is the same boundary-based approach used in the current `buildMultiSourceSegments`.

```
Input text:  "Alice went to Wonderland"
Label A:     [0, 5)   "Alice"   style: { color: blue }
Label B:     [3, 14)  "ce went to" style: { color: red }

Boundaries:  0, 3, 5, 14, 24

Segments:
  [0, 3)   "Ali"              → labels: [A],    style: A.style
  [3, 5)   "ce"               → labels: [A, B], style: combine(A.style, B.style)
  [5, 14)  " went to "        → labels: [B],    style: B.style
  [14, 24) "Wonderland"       → labels: [],     style: empty
```

Algorithm:

1. Collect all label `start` and `end` positions, plus `0` and `text.length`, into a set of boundary points.
2. Sort the boundary points.
3. For each pair of consecutive boundaries `[start, end)`:
   - Find all labels where `label.start <= start && label.end >= end`.
   - Fold their styles: `labels.reduce((acc, l) => combine(acc, l.style), empty)`.
   - Emit a `StyledSegment`.

This runs in `O(B * L)` where `B` is the number of boundary points and `L` is the number of labels. For typical chapter sizes (a few hundred labels), this is fast. We can optimize this by using a segment tree.

---

## Rendering

The top-level React component:

```typescript
type LabeledTextProps<S, L extends LabelSpan = LabelSpan> = {
  text: string;
  styledLabels: StyledLabel<S, L>[];
  styleConfig: StyleConfig<S>;
  renderSegment?: SegmentRenderer<S, L>;
  onTextSelect?: (selection: TextSelection) => void;
  onLabelClick?: (label: L, rect: DOMRect) => void;
};
```

The `renderSegment` prop is optional. The library provides a default renderer that maps style fields to CSS properties (background color, underline, opacity, etc.). Users can override it for custom rendering strategies like gradients, animations, or entirely different visual approaches.

The component handles:

- Running the segmentation algorithm
- Rendering each segment via `renderSegment`
- Text selection tracking (mapping DOM selections back to character positions via `data-char-start` attributes)
- Label click detection (delegated to `onLabelClick`)

---

## Examples

### Simple: single color per label

```typescript
type SimpleStyle = { color: string; opacity: number };

const simpleConfig: StyleConfig<SimpleStyle> = {
  empty: { color: "transparent", opacity: 1 },
  combine: (a, b) => ({
    color: a.color === "transparent" ? b.color : a.color,
    opacity: Math.min(a.opacity, b.opacity),
  }),
};
```

### Priority-aware: higher priority overrides color

```typescript
type PriorityStyle = { color: string; opacity: number; priority: number };

const priorityConfig: StyleConfig<PriorityStyle> = {
  empty: { color: "transparent", opacity: 1, priority: Infinity },
  combine: (a, b) => {
    const winner = a.priority <= b.priority ? a : b;
    const loser = a.priority <= b.priority ? b : a;
    return {
      color: winner.color,
      opacity: (winner.opacity + loser.opacity) / 2,
      priority: winner.priority,
    };
  },
};
```

### NovelTL-specific: active tab emphasized

```typescript
type NovelTLStyle = {
  color: string;
  emphasis: "bright" | "dim";
  priority: number;
  interactive: boolean;
};

const novelTLConfig: StyleConfig<NovelTLStyle> = {
  empty: { color: "transparent", emphasis: "dim", priority: Infinity, interactive: false },
  combine: (a, b) => {
    const primary = a.priority <= b.priority ? a : b;
    return {
      color: primary.color,
      emphasis: primary.emphasis,
      priority: primary.priority,
      interactive: primary.interactive || (a.priority <= b.priority ? b : a).interactive,
    };
  },
};

// Usage: the active tab's label group gets priority 0, emphasis "bright"
// All other groups get priority 1, emphasis "dim"
```

---

## Integration with NovelTL

The current code maps to the library as follows:

| Current code | Library equivalent |
|---|---|
| `LabelSourceConfig` | `StyledLabel<S>` — labels paired with styles |
| `buildMultiSourceSegments` | `buildStyledSegments` — the segmentation algorithm |
| `resolveSegmentStyle` | `StyleConfig.combine` — the monoid operation |
| `AnnotatedText` | `LabeledText` — the top-level component |
| `ActiveSource.priority` | A field inside the user-defined `S` type |

Migration path: replace `labelOps.ts` internals with the library, define a `NovelTLStyle` type and its `StyleConfig`, and pass them to `LabeledText`. The workspace page (`NovelWorkspacePage.tsx`) constructs `StyledLabel[]` from its label groups and NER results, choosing emphasis/priority based on the active tab.

---

## Editing Integration

Text editing and label display are separate concerns. The library handles display; editing is handled by a sibling component (currently `InlineTextEditor`). They share the same text data but never render simultaneously — when the user is editing, the textarea is shown; when viewing labels, `LabeledText` is shown.

The library does not need to know about editing, revision text IDs, or concurrency control. It takes a `text` string and `StyledLabel[]` and renders them.

---

## Future: Style Transform Step

An optional preprocessing step that enriches styles with context-dependent data before segmentation. The pipeline becomes:

```
PureStyle (stored)  →  transform(text, labels)  →  Style (enriched)  →  segment + combine  →  render
```

This would add a second type parameter:

```typescript
type LabeledTextProps<P, S = P, L extends LabelSpan = LabelSpan> = {
  text: string;
  styledLabels: StyledLabel<P, L>[];
  styleConfig: StyleConfig<S>;
  transform?: (text: string, labels: StyledLabel<P, L>[]) => StyledLabel<S, L>[];
  renderSegment?: SegmentRenderer<S, L>;
  // ...
};
```

When `transform` is not provided (default), `P === S` and the labels pass through unchanged. TypeScript default type parameters (`S = P`) mean simple usage doesn't pay for this complexity.

Use cases: gradient blending between adjacent labels, context-dependent emphasis (e.g., labels near the cursor get brighter). This is not planned for the initial implementation.

---

## Package Structure

The library can be published as a standalone package with no NovelTL dependencies:

```
labeled-text/
  src/
    core.ts              # StyleConfig, StyledLabel, StyledSegment types
    segment.ts           # buildStyledSegments (pure function, no React)
    react/
      LabeledText.tsx    # Top-level component
      defaultRenderer.tsx  # Default SegmentRenderer
      selection.ts       # Text selection → character position mapping
  package.json
```

The `core.ts` and `segment.ts` modules have zero dependencies. The `react/` directory depends only on React. NovelTL imports the library and provides its own `StyleConfig` and optionally its own `SegmentRenderer`.

---

## Relevant Files

- `frontend/src/components/workspace/labelOps.ts` — Current label segmentation and style resolution (to be replaced)
- `frontend/src/components/workspace/AnnotatedText.tsx` — Current annotated text display component (to be replaced)
- `frontend/src/types/label.ts` — Label type definitions (library will use a generic `LabelSpan` instead)
- `frontend/src/components/workspace/InlineTextEditor.tsx` — Text editing component (stays separate)
- `frontend/src/pages/NovelWorkspacePage.tsx` — Consumer that constructs label sources and styles

## See Also

- [workspace-implementation.md](workspace-implementation.md) — How the current workspace is built, including label rendering pipeline
- [ui-requirements.md](ui-requirements.md) — Frontend component specs and UX workflows
- [editable-with-labels.md](editable-with-labels.md) — Label offset adjustment when text is edited