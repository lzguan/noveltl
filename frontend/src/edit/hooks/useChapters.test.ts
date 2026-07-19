import { act, renderHook } from "@testing-library/react";
import { Prov } from "../controller/types/helperTypes";
import { CProvId } from "../controller/types/idTypes";
import { useChapters } from "./useChapters";

const CHAPTER_A = CProvId("chapter-a");
const CHAPTER_B = CProvId("chapter-b");
const CHAPTER_C = CProvId("chapter-c");

function chapter(chapterId: CProvId, chapterNum: number) {
	return Prov({
		chapterId,
		chapterNum,
		chapterTitle: `Chapter ${chapterNum}`,
		chapterIsPublic: false,
		novelId: "novel",
	});
}

describe("useChapters", () => {
	it("removes an active chapter from the list and tabs and selects the adjacent tab", () => {
		const { result } = renderHook(() => useChapters());

		act(() => {
			result.current.addChapter(chapter(CHAPTER_A, 1));
			result.current.addChapter(chapter(CHAPTER_B, 2));
			result.current.addChapter(chapter(CHAPTER_C, 3));
			result.current.updateTabs([
				{ chapterId: CHAPTER_A, status: "ready" },
				{ chapterId: CHAPTER_B, status: "ready" },
				{ chapterId: CHAPTER_C, status: "ready" },
			]);
			result.current.updateActive(CHAPTER_B);
			result.current.removeChapter(CHAPTER_B);
		});

		expect(result.current.chapterList.map((item) => item.chapterId)).toEqual([
			CHAPTER_A,
			CHAPTER_C,
		]);
		expect(result.current.tabs.map((tab) => tab.chapterId)).toEqual([CHAPTER_A, CHAPTER_C]);
		expect(result.current.activeChapterId).toBe(CHAPTER_C);
	});

	it("preserves the active chapter when removing a different chapter", () => {
		const { result } = renderHook(() => useChapters());

		act(() => {
			result.current.addChapter(chapter(CHAPTER_A, 1));
			result.current.addChapter(chapter(CHAPTER_B, 2));
			result.current.updateTabs([
				{ chapterId: CHAPTER_A, status: "ready" },
				{ chapterId: CHAPTER_B, status: "ready" },
			]);
			result.current.updateActive(CHAPTER_A);
			result.current.removeChapter(CHAPTER_B);
		});

		expect(result.current.chapterList.map((item) => item.chapterId)).toEqual([CHAPTER_A]);
		expect(result.current.tabs.map((tab) => tab.chapterId)).toEqual([CHAPTER_A]);
		expect(result.current.activeChapterId).toBe(CHAPTER_A);
	});
});
