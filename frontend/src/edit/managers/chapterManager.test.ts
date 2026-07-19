import { act, renderHook } from "@testing-library/react";
import { Effect } from "effect";
import type {
	NovelGetters,
	NovelUserEvent,
	TriggerEvent,
} from "../controller/types/controllerTypes";
import { CProvId } from "../controller/types/idTypes";
import { useChapters } from "../hooks/useChapters";
import { createChapterManager } from "./chapterManager";

const CHAPTER_A = CProvId("chapter-a");
const CHAPTER_B = CProvId("chapter-b");
const CHAPTER_C = CProvId("chapter-c");

const unusedGetter = () => Effect.die("unused getter");
const getters: NovelGetters = {
	novel: unusedGetter,
	role: unusedGetter,
	labelGroupIds: unusedGetter,
	chapterIds: unusedGetter,
	chapterGetterSlot: unusedGetter,
	labelGroupSlot: unusedGetter,
	autoLabelRunIds: unusedGetter,
	autoLabelRunSlot: unusedGetter,
};

function setup() {
	const chapters = renderHook(() => useChapters());
	const controllerEvents: NovelUserEvent[] = [];
	const manager = createChapterManager({
		controllerUserEvent: (event) => {
			controllerEvents.push(event);
		},
		chapters: chapters.result.current,
		setLoading: () => {},
		labelGroupsRef: { current: new Map() },
	});
	const handleControllerEvent = (event: TriggerEvent) => {
		Effect.runSync(manager.handleControllerEvent(getters, event));
	};
	return { chapters, controllerEvents, manager, handleControllerEvent };
}

describe("createChapterManager", () => {
	it("opens tabs once and focuses an existing ready tab", () => {
		const { chapters, manager, handleControllerEvent } = setup();

		act(() => {
			manager.switchChapter(CHAPTER_A);
			handleControllerEvent({
				eventType: "chapterOpened",
				chapterId: CHAPTER_A,
				flags: { forEditor: true },
			});
			manager.switchChapter(CHAPTER_B);
			handleControllerEvent({
				eventType: "chapterOpened",
				chapterId: CHAPTER_B,
				flags: { forEditor: true },
			});
			manager.switchChapter(CHAPTER_A);
		});

		expect(chapters.result.current.tabs.map((tab) => tab.chapterId)).toEqual([
			CHAPTER_A,
			CHAPTER_B,
		]);
		expect(chapters.result.current.activeChapterId).toBe(CHAPTER_A);
	});

	it("selects the right tab, then the left tab, when closing the active tab", () => {
		const { chapters, manager, handleControllerEvent } = setup();

		act(() => {
			for (const chapterId of [CHAPTER_A, CHAPTER_B, CHAPTER_C]) {
				manager.switchChapter(chapterId);
				handleControllerEvent({
					eventType: "chapterOpened",
					chapterId,
					flags: { forEditor: true },
				});
			}
			manager.switchChapter(CHAPTER_B);
			manager.closeChapter(CHAPTER_B);
		});
		expect(chapters.result.current.activeChapterId).toBe(CHAPTER_C);

		act(() => {
			manager.closeChapter(CHAPTER_C);
		});
		expect(chapters.result.current.activeChapterId).toBe(CHAPTER_A);
	});

	it("defers reopening until cache eviction finishes", () => {
		const { chapters, controllerEvents, manager, handleControllerEvent } = setup();

		act(() => {
			manager.switchChapter(CHAPTER_A);
			handleControllerEvent({
				eventType: "chapterOpened",
				chapterId: CHAPTER_A,
				flags: { forEditor: true },
			});
			manager.closeChapter(CHAPTER_A);
		});
		const eventCountAfterClose = controllerEvents.length;

		act(() => {
			manager.switchChapter(CHAPTER_A);
		});
		expect(chapters.result.current.tabs).toEqual([{ chapterId: CHAPTER_A, status: "loading" }]);
		expect(controllerEvents).toHaveLength(eventCountAfterClose);

		act(() => {
			handleControllerEvent({
				eventType: "chapterClosed",
				chapterId: CHAPTER_A,
			});
		});
		expect(controllerEvents).toHaveLength(eventCountAfterClose + 1);
		expect(controllerEvents.at(-1)).toMatchObject({
			eventType: "openChapter",
			chapterId: CHAPTER_A,
		});
	});
});
