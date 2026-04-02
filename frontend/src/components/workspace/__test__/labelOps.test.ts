import { describe, it, expect } from "vitest";
import { buildSegments, getEntityGroupColor, applyOpToLabels, buildMultiSourceSegments, resolveSegmentStyle, NER_RESULTS_COLOR, type LabelSourceConfig, type ActiveSource } from "../labelOps";
import { type Label, type AddLabelOp, type DeleteLabelOp, type UpdateLabelOp } from "../../../types/label";

const makeLabel = (start: number, end: number, word: string, opts?: Partial<Label>): Label => ({
    labelEntityGroup: opts?.labelEntityGroup ?? "PER",
    labelScore: opts?.labelScore ?? 0.9,
    labelWord: word,
    labelStart: start,
    labelEnd: end,
    labelDirty: opts?.labelDirty ?? false,
});

describe("buildSegments", () => {
    it("returns a single plain segment when no labels", () => {
        const segments = buildSegments("hello world", []);
        expect(segments).toEqual([
            { type: "plain", text: "hello world", charStart: 0, charEnd: 11 },
        ]);
    });

    it("splits text around a single label", () => {
        const label = makeLabel(6, 11, "world");
        const segments = buildSegments("hello world", [label]);
        expect(segments).toHaveLength(2);
        expect(segments[0]).toEqual({ type: "plain", text: "hello ", charStart: 0, charEnd: 6 });
        expect(segments[1]).toEqual({ type: "label", text: "world", charStart: 6, charEnd: 11, label });
    });

    it("handles label at start of text", () => {
        const label = makeLabel(0, 5, "hello");
        const segments = buildSegments("hello world", [label]);
        expect(segments).toHaveLength(2);
        expect(segments[0]).toEqual({ type: "label", text: "hello", charStart: 0, charEnd: 5, label });
        expect(segments[1]).toEqual({ type: "plain", text: " world", charStart: 5, charEnd: 11 });
    });

    it("handles multiple non-overlapping labels", () => {
        const l1 = makeLabel(0, 5, "hello");
        const l2 = makeLabel(6, 11, "world");
        const segments = buildSegments("hello world", [l1, l2]);
        expect(segments).toHaveLength(3);
        expect(segments[0]).toEqual({ type: "label", text: "hello", charStart: 0, charEnd: 5, label: l1 });
        expect(segments[1]).toEqual({ type: "plain", text: " ", charStart: 5, charEnd: 6 });
        expect(segments[2]).toEqual({ type: "label", text: "world", charStart: 6, charEnd: 11, label: l2 });
    });

    it("skips overlapping labels", () => {
        const l1 = makeLabel(0, 7, "hello w");
        const l2 = makeLabel(5, 11, " world");
        const segments = buildSegments("hello world", [l1, l2]);
        expect(segments).toHaveLength(2);
        expect(segments[0]).toEqual({ type: "label", text: "hello w", charStart: 0, charEnd: 7, label: l1 });
        expect(segments[1]).toEqual({ type: "plain", text: "orld", charStart: 7, charEnd: 11 });
    });

    it("sorts labels by start position regardless of input order", () => {
        const l1 = makeLabel(6, 11, "world");
        const l2 = makeLabel(0, 5, "hello");
        const segments = buildSegments("hello world", [l1, l2]);
        expect(segments[0]).toEqual({ type: "label", text: "hello", charStart: 0, charEnd: 5, label: l2 });
    });
});

describe("getEntityGroupColor", () => {
    it("returns blue for PER", () => {
        expect(getEntityGroupColor("PER")).toBe("#4a90d9");
    });

    it("returns green for LOC", () => {
        expect(getEntityGroupColor("LOC")).toBe("#27ae60");
    });

    it("is case-insensitive", () => {
        expect(getEntityGroupColor("per")).toBe("#4a90d9");
        expect(getEntityGroupColor("Loc")).toBe("#27ae60");
    });

    it("returns default color for unknown group", () => {
        expect(getEntityGroupColor("CUSTOM")).toBe("#7f8c8d");
    });

    it("returns default color for null", () => {
        expect(getEntityGroupColor(null)).toBe("#7f8c8d");
    });
});

describe("applyOpToLabels", () => {
    const existing: Label[] = [
        makeLabel(0, 5, "hello", { labelEntityGroup: "PER" }),
        makeLabel(6, 11, "world", { labelEntityGroup: "LOC" }),
    ];

    it("adds a new label", () => {
        const op: AddLabelOp = { op: "add", startPos: 12, endPos: 17, word: "again", entityGroup: "ORG", score: 0.8 };
        const result = applyOpToLabels(existing, op);
        expect(result).toHaveLength(3);
        expect(result[2]).toEqual({
            labelEntityGroup: "ORG",
            labelScore: 0.8,
            labelWord: "again",
            labelStart: 12,
            labelEnd: 17,
            labelDirty: true,
        });
    });

    it("deletes a label by position and word", () => {
        const op: DeleteLabelOp = { op: "delete", startPos: 0, endPos: 5, word: "hello" };
        const result = applyOpToLabels(existing, op);
        expect(result).toHaveLength(1);
        expect(result[0].labelWord).toBe("world");
    });

    it("updates a label's entity group", () => {
        const op: UpdateLabelOp = { op: "update", startPos: 0, endPos: 5, word: "hello", entityGroup: "ORG" };
        const result = applyOpToLabels(existing, op);
        expect(result[0].labelEntityGroup).toBe("ORG");
        expect(result[1].labelEntityGroup).toBe("LOC");
    });

    it("update preserves fields not specified in the op", () => {
        const op: UpdateLabelOp = { op: "update", startPos: 0, endPos: 5, word: "hello", dirty: true };
        const result = applyOpToLabels(existing, op);
        expect(result[0].labelDirty).toBe(true);
        expect(result[0].labelEntityGroup).toBe("PER");
        expect(result[0].labelScore).toBe(0.9);
    });
});

const makeSource = (
    sourceKey: string,
    labels: Label[],
    opts?: Partial<Omit<LabelSourceConfig, "sourceKey" | "labels">>
): LabelSourceConfig => ({
    sourceKey,
    labels,
    style: opts?.style ?? "bright",
    mode: opts?.mode ?? "highlight",
    interactive: opts?.interactive ?? false,
    priority: opts?.priority ?? 0,
});

describe("buildMultiSourceSegments", () => {
    it("returns segments covering full text when no sources", () => {
        const segments = buildMultiSourceSegments("hello world", []);
        expect(segments).toHaveLength(1);
        expect(segments[0]).toEqual({
            text: "hello world",
            charStart: 0,
            charEnd: 11,
            activeSources: [],
        });
    });

    it("builds segments for a single source with one label", () => {
        const label = makeLabel(6, 11, "world");
        const source = makeSource("labelsTab", [label], { interactive: true, priority: 0 });
        const segments = buildMultiSourceSegments("hello world", [source]);

        expect(segments).toHaveLength(2);
        expect(segments[0].text).toBe("hello ");
        expect(segments[0].activeSources).toHaveLength(0);
        expect(segments[1].text).toBe("world");
        expect(segments[1].activeSources).toHaveLength(1);
        expect(segments[1].activeSources[0].sourceKey).toBe("labelsTab");
        expect(segments[1].activeSources[0].label).toBe(label);
    });

    it("handles two overlapping sources with correct priority ordering", () => {
        const l1 = makeLabel(0, 5, "hello", { labelEntityGroup: "PER" });
        const l2 = makeLabel(3, 8, "lo wo", { labelEntityGroup: "LOC" });
        const s1 = makeSource("labelsTab", [l1], { priority: 0 });
        const s2 = makeSource("nerResults", [l2], { priority: 1 });
        const segments = buildMultiSourceSegments("hello world", [s1, s2]);

        // Boundaries: 0, 3, 5, 8, 11
        expect(segments).toHaveLength(4);

        // [0,3) — only s1
        expect(segments[0].text).toBe("hel");
        expect(segments[0].activeSources).toHaveLength(1);
        expect(segments[0].activeSources[0].sourceKey).toBe("labelsTab");

        // [3,5) — both sources, s1 first (priority 0)
        expect(segments[1].text).toBe("lo");
        expect(segments[1].activeSources).toHaveLength(2);
        expect(segments[1].activeSources[0].sourceKey).toBe("labelsTab");
        expect(segments[1].activeSources[1].sourceKey).toBe("nerResults");

        // [5,8) — only s2
        expect(segments[2].text).toBe(" wo");
        expect(segments[2].activeSources).toHaveLength(1);
        expect(segments[2].activeSources[0].sourceKey).toBe("nerResults");

        // [8,11) — no sources
        expect(segments[3].text).toBe("rld");
        expect(segments[3].activeSources).toHaveLength(0);
    });

    it("handles adjacent labels from different sources", () => {
        const l1 = makeLabel(0, 5, "hello");
        const l2 = makeLabel(5, 6, " ");
        const s1 = makeSource("labelsTab", [l1]);
        const s2 = makeSource("nerTabGroup", [l2]);
        const segments = buildMultiSourceSegments("hello world", [s1, s2]);

        const labeled = segments.filter((s) => s.activeSources.length > 0);
        expect(labeled).toHaveLength(2);
        expect(labeled[0].text).toBe("hello");
        expect(labeled[0].activeSources[0].sourceKey).toBe("labelsTab");
        expect(labeled[1].text).toBe(" ");
        expect(labeled[1].activeSources[0].sourceKey).toBe("nerTabGroup");
    });

    it("skips within-source overlap (takes first label only per source)", () => {
        // Two labels from same source that overlap — only the one covering the segment is used
        const l1 = makeLabel(0, 7, "hello w");
        const l2 = makeLabel(3, 11, "lo world");
        const source = makeSource("labelsTab", [l1, l2]);
        const segments = buildMultiSourceSegments("hello world", [source]);

        // Boundaries: 0, 3, 7, 11
        // [0,3) → l1 covers, [3,7) → l1 covers (break after first match), [7,11) → l2 covers
        expect(segments).toHaveLength(3);
        expect(segments[0].activeSources[0].label).toBe(l1);
        expect(segments[1].activeSources[0].label).toBe(l1);
        expect(segments[2].activeSources[0].label).toBe(l2);
    });
});

describe("resolveSegmentStyle", () => {
    const makeActiveSource = (
        sourceKey: string,
        label: Label,
        opts?: Partial<Omit<ActiveSource, "sourceKey" | "label">>
    ): ActiveSource => ({
        sourceKey,
        label,
        style: opts?.style ?? "bright",
        mode: opts?.mode ?? "highlight",
        interactive: opts?.interactive ?? false,
        priority: opts?.priority ?? 0,
    });

    it("returns empty css for no active sources", () => {
        const result = resolveSegmentStyle([]);
        expect(result.css).toEqual({});
        expect(result.interactiveSource).toBeNull();
    });

    it("applies bright highlight for single bright source", () => {
        const label = makeLabel(0, 5, "hello", { labelEntityGroup: "PER" });
        const source = makeActiveSource("labelsTab", label, { style: "bright" });
        const result = resolveSegmentStyle([source]);

        expect(result.css.backgroundColor).toBe("#4a90d933");
        expect(result.css.borderBottom).toBe("2px solid #4a90d9");
    });

    it("applies dim highlight for single dim source", () => {
        const label = makeLabel(0, 5, "hello", { labelEntityGroup: "LOC" });
        const source = makeActiveSource("labelsTab", label, { style: "dim" });
        const result = resolveSegmentStyle([source]);

        expect(result.css.backgroundColor).toBe("#27ae6015");
        expect(result.css.borderBottom).toBe("1px dashed #27ae60");
    });

    it("uses NER_RESULTS_COLOR for nerResults source", () => {
        const label = makeLabel(0, 5, "hello");
        const source = makeActiveSource("nerResults", label, { style: "bright" });
        const result = resolveSegmentStyle([source]);

        expect(result.css.backgroundColor).toBe(`${NER_RESULTS_COLOR}33`);
        expect(result.css.borderBottom).toBe(`2px solid ${NER_RESULTS_COLOR}`);
    });

    it("identifies the interactive source", () => {
        const label = makeLabel(0, 5, "hello");
        const s1 = makeActiveSource("nerResults", label, { interactive: false, priority: 0 });
        const s2 = makeActiveSource("labelsTab", label, { interactive: true, priority: 1 });
        const result = resolveSegmentStyle([s1, s2]);

        expect(result.interactiveSource).toBe(s2);
        expect(result.css.cursor).toBe("pointer");
    });

    it("highest-priority source gets background, lower gets underline", () => {
        const l1 = makeLabel(0, 5, "hello", { labelEntityGroup: "PER" });
        const l2 = makeLabel(0, 5, "hello", { labelEntityGroup: "LOC" });
        const s1 = makeActiveSource("labelsTab", l1, { style: "bright", priority: 0 });
        const s2 = makeActiveSource("nerTabGroup", l2, { style: "dim", priority: 1 });
        const result = resolveSegmentStyle([s1, s2]);

        // Primary (labelsTab PER) gets background
        expect(result.css.backgroundColor).toBe("#4a90d933");
        // Primary's underline comes first
        expect(result.css.borderBottom).toBe("2px solid #4a90d9");
    });
});
