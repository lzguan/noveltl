import { describe, it, expect } from "vitest";
import { diffToTextOps } from "../diffToTextOps";
import { type TextOp } from "../../../types/novel";

/** Apply ops sequentially to verify they produce the expected text. */
function applyOps(text: string, ops: TextOp[]): string {
    for (const op of ops) {
        if (op.op === "delete") {
            text = text.slice(0, op.start) + text.slice(op.start + op.text.length);
        } else {
            text = text.slice(0, op.start) + op.text + text.slice(op.start);
        }
    }
    return text;
}

describe("diffToTextOps", () => {
    it("returns empty array for identical strings", () => {
        expect(diffToTextOps("hello", "hello")).toEqual([]);
    });

    it("returns empty array for two empty strings", () => {
        expect(diffToTextOps("", "")).toEqual([]);
    });

    it("handles pure insertion at end", () => {
        const ops = diffToTextOps("hello", "hello world");
        expect(applyOps("hello", ops)).toBe("hello world");
        expect(ops.every((op) => op.op === "insert")).toBe(true);
    });

    it("handles pure insertion at start", () => {
        const ops = diffToTextOps("world", "hello world");
        expect(applyOps("world", ops)).toBe("hello world");
    });

    it("handles pure deletion at end", () => {
        const ops = diffToTextOps("hello world", "hello");
        expect(applyOps("hello world", ops)).toBe("hello");
        expect(ops.every((op) => op.op === "delete")).toBe(true);
    });

    it("handles pure deletion at start", () => {
        const ops = diffToTextOps("hello world", "world");
        expect(applyOps("hello world", ops)).toBe("world");
    });

    it("handles replacement (delete + insert)", () => {
        const ops = diffToTextOps("hello world", "hello earth");
        expect(applyOps("hello world", ops)).toBe("hello earth");
    });

    it("handles insertion from empty string", () => {
        const ops = diffToTextOps("", "new text");
        expect(applyOps("", ops)).toBe("new text");
    });

    it("handles deletion to empty string", () => {
        const ops = diffToTextOps("old text", "");
        expect(applyOps("old text", ops)).toBe("");
    });

    it("handles multiple scattered edits", () => {
        const old = "The quick brown fox jumps over the lazy dog";
        const next = "The slow brown cat jumps over the happy dog";
        const ops = diffToTextOps(old, next);
        expect(applyOps(old, ops)).toBe(next);
    });

    it("handles insertion in the middle", () => {
        const ops = diffToTextOps("abcdef", "abc123def");
        expect(applyOps("abcdef", ops)).toBe("abc123def");
    });

    it("handles deletion in the middle", () => {
        const ops = diffToTextOps("abc123def", "abcdef");
        expect(applyOps("abc123def", ops)).toBe("abcdef");
    });

    it("handles complete replacement", () => {
        const ops = diffToTextOps("entirely different", "completely new text");
        expect(applyOps("entirely different", ops)).toBe("completely new text");
    });

    it("handles unicode text", () => {
        const old = "在北京的张三说了一句话";
        const next = "第一章：在北京的张三说了一句话";
        const ops = diffToTextOps(old, next);
        expect(applyOps(old, ops)).toBe(next);
    });

    it("handles multiline text with line additions", () => {
        const old = "line 1\nline 2\nline 3";
        const next = "line 1\nnew line\nline 2\nline 3";
        const ops = diffToTextOps(old, next);
        expect(applyOps(old, ops)).toBe(next);
    });

    it("handles pirate-site filler removal (key use case)", () => {
        const old = [
            "He picked up a pen.",
            "Read at SuperNovelz.biz! Support us!",
            "Lightning struck him.",
        ].join("\n");
        const next = "He picked up a pen.\nLightning struck him.";
        const ops = diffToTextOps(old, next);
        expect(applyOps(old, ops)).toBe(next);
    });
});
