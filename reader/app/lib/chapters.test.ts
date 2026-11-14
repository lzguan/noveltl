import { describe, expect, it } from "vitest";
import { locateChapter, parseChapterNum, splitParagraphs } from "./chapters";

const chapter = (chapterNum: number) => ({
	chapterId: `id-${chapterNum}`,
	chapterNum,
	chapterTitle: `Title ${chapterNum}`,
});

describe("locateChapter", () => {
	const chapters = [chapter(5), chapter(1), chapter(2)];

	it("finds neighbours by chapter number across gaps and unsorted input", () => {
		const position = locateChapter(chapters, 2);
		expect(position?.current.chapterId).toBe("id-2");
		expect(position?.prev?.chapterNum).toBe(1);
		expect(position?.next?.chapterNum).toBe(5);
	});

	it("has no prev at the start and no next at the end", () => {
		expect(locateChapter(chapters, 1)?.prev).toBeNull();
		expect(locateChapter(chapters, 5)?.next).toBeNull();
	});

	it("returns null for a missing chapter", () => {
		expect(locateChapter(chapters, 3)).toBeNull();
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
