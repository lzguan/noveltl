import { describe, it, expect } from "vitest";
import { buildSegments, getEntityGroupColor, applyOpToLabels } from "../labelOps";
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
