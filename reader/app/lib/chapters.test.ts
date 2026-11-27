import { describe, expect, it } from "vitest";
import { chapterLabel, parseChapterNum, sortChapters, splitParagraphs } from "./chapters";

describe("sortChapters", () => {
	it("orders chapters by chapter number across gaps without mutating input", () => {
		const chapters = [
			{ chapterNum: 5, title: "Title 5" },
			{ chapterNum: 1, title: "Title 1" },
			{ chapterNum: 2, title: "Title 2" },
		];
		expect(sortChapters(chapters).map((chapter) => chapter.chapterNum)).toEqual([1, 2, 5]);
		expect(chapters.map((chapter) => chapter.chapterNum)).toEqual([5, 1, 2]);
	});
});

describe("chapterLabel", () => {
	it("uses trimmed title or falls back to chapter number", () => {
		expect(chapterLabel({ chapterNum: 3, title: "  Awakening  " })).toBe("Awakening");
		expect(chapterLabel({ chapterNum: 3, title: "   " })).toBe("Chapter 3");
	});
});

describe("parseChapterNum", () => {
	it("accepts plain non-negative integers only", () => {
		expect(parseChapterNum("12")).toBe(12);
		expect(parseChapterNum("0")).toBe(0);
		expect(parseChapterNum("1.5")).toBeNull();
		expect(parseChapterNum("-1")).toBeNull();
		expect(parseChapterNum("abc")).toBeNull();
		expect(parseChapterNum(undefined)).toBeNull();
	});
});

describe("splitParagraphs", () => {
	it("splits on newlines and drops blank lines", () => {
		expect(splitParagraphs("  One\r\n\n Two \n\n")).toEqual(["One", "Two"]);
	});
});
