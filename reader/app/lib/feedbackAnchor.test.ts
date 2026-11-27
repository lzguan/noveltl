import { describe, expect, it } from "vitest";
import { extractWordAnchor } from "./feedbackAnchor";

describe("extractWordAnchor", () => {
	it("extracts a Latin word at start, middle, and trailing edge", () => {
		const text = "The moon rose over the quiet valley.";
		expect(extractWordAnchor(text, 2, 4)).toEqual({
			paragraphIndex: 2,
			startOffset: 4,
			endOffset: 8,
			quote: "moon",
		});
		expect(extractWordAnchor(text, 2, 6)).toEqual({
			paragraphIndex: 2,
			startOffset: 4,
			endOffset: 8,
			quote: "moon",
		});
		// Trailing space right after "moon" snaps to "moon"
		expect(extractWordAnchor(text, 2, 8)).toEqual({
			paragraphIndex: 2,
			startOffset: 4,
			endOffset: 8,
			quote: "moon",
		});
	});

	it("preserves internal apostrophes and hyphens", () => {
		const text = "He didn't trust the well-known alchemist.";
		expect(extractWordAnchor(text, 0, 5)).toEqual({
			paragraphIndex: 0,
			startOffset: 3,
			endOffset: 9,
			quote: "didn't",
		});
		expect(extractWordAnchor(text, 0, 24)).toEqual({
			paragraphIndex: 0,
			startOffset: 20,
			endOffset: 30,
			quote: "well-known",
		});
	});

	it("clamps out-of-bounds offsets cleanly", () => {
		const text = "Dawn broke.";
		expect(extractWordAnchor(text, 0, -10)).toEqual({
			paragraphIndex: 0,
			startOffset: 0,
			endOffset: 4,
			quote: "Dawn",
		});
		expect(extractWordAnchor(text, 0, 999)).toEqual({
			paragraphIndex: 0,
			startOffset: 5,
			endOffset: 10,
			quote: "broke",
		});
	});

	it("handles CJK phrases gracefully without returning the entire sentence", () => {
		const text = "林枫站在山巅望着远方的云海。";
		const anchor = extractWordAnchor(text, 1, 5);
		expect(anchor).not.toBeNull();
		if (anchor) {
			expect(anchor.paragraphIndex).toBe(1);
			expect(anchor.endOffset).toBeGreaterThan(anchor.startOffset);
			expect(anchor.quote).toBe(text.slice(anchor.startOffset, anchor.endOffset));
			expect(anchor.quote.length).toBeGreaterThan(0);
			expect(anchor.quote.length).toBeLessThan(text.length);
		}
	});

	it("handles Korean Hangul space-separated words", () => {
		const text = "검은 달빛이 계곡을 비추었다.";
		expect(extractWordAnchor(text, 0, 4)).toEqual({
			paragraphIndex: 0,
			startOffset: 3,
			endOffset: 6,
			quote: "달빛이",
		});
	});

	it("returns null for blank paragraphs or negative paragraph indices", () => {
		expect(extractWordAnchor("", 0, 0)).toBeNull();
		expect(extractWordAnchor("   \t\n  ", 0, 2)).toBeNull();
		expect(extractWordAnchor("Hello world", -1, 0)).toBeNull();
	});

	it("clamps very long tokens to 300 characters", () => {
		const longWord = "a".repeat(400);
		const anchor = extractWordAnchor(longWord, 0, 50);
		expect(anchor).toEqual({
			paragraphIndex: 0,
			startOffset: 0,
			endOffset: 300,
			quote: "a".repeat(300),
		});
	});
});
