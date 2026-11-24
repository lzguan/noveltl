import { act, renderHook } from "@testing-library/react";
import { Effect } from "effect";
import type {
	NovelGetters,
	NovelUserEvent,
	TriggerEvent,
} from "../controller/types/controllerTypes";
import { Prov } from "../controller/types/helperTypes";
import { CCProvId, CCServId, CProvId, CServId } from "../controller/types/idTypes";
import { useChapters } from "../hooks/useChapters";
import { createChapterManager } from "./chapterManager";

const CHAPTER_A = CProvId("chapter-a");
const CHAPTER_B = CProvId("chapter-b");
const CHAPTER_C = CProvId("chapter-c");

const unusedGetter = () => Effect.die("unused getter");
function makeGetters(overrides: Partial<NovelGetters> = {}): NovelGetters {
	return {
		novel: unusedGetter,
		role: unusedGetter,
		labelGroupIds: unusedGetter,
		chapterIds: unusedGetter,
		chapterIdFromServerId: unusedGetter,
		chapterServerId: () => Effect.succeed(null),
		chapterContentServerId: () => Effect.succeed(null),
		chapterContentIdFromServerId: unusedGetter,
		labelIdFromServerId: unusedGetter,
		labelGroupIdFromServerId: unusedGetter,
		labelGroupServerId: unusedGetter,
		chapterGetterSlot: unusedGetter,
		labelGroupSlot: unusedGetter,
		...overrides,
	};
}

function setup(getterOverrides: Partial<NovelGetters> = {}) {
	const chapters = renderHook(() => useChapters());
	const controllerEvents: NovelUserEvent[] = [];
	const getters = makeGetters(getterOverrides);
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

	it("tracks open chapter content IDs across open, text edits, reopen, and close", () => {
		const CHAPTER_SERV_ID = CServId("chapter-serv-a");
		let currentCCProvId = CCProvId("cc-prov-1");
		let currentCCServId: CCServId | null = CCServId("cc-serv-1");
		let textSynced = true;

		const { chapters, handleControllerEvent } = setup({
			chapterServerId: (id) => Effect.succeed(id === CHAPTER_A ? CHAPTER_SERV_ID : null),
			chapterContentServerId: (id) =>
				Effect.succeed(id === CHAPTER_A ? currentCCServId : null),
			chapterGetterSlot: () =>
				Effect.succeed({
					status: "ready",
					inFlight: 0,
					meta: {
						chapter: Prov({
							chapterId: CHAPTER_A,
							novelId: "novel-1",
							chapterNum: 1,
							chapterTitle: "Chapter 1",
							chapterIsPublic: true,
						}),
					},
					data: {
						chapterGetters: {
							chapterContentId: () => Effect.succeed(currentCCProvId),
							text: () => Effect.succeed("hello"),
							isTextSynced: () => textSynced,
							isDestroyed: () => false,
							labelGroupIds: () => Effect.succeed([]),
							labelDataSlot: unusedGetter,
							labelDataMeta: unusedGetter,
						},
					},
				}),
		});

		act(() => {
			handleControllerEvent({
				eventType: "chapterOpened",
				chapterId: CHAPTER_A,
				flags: { forEditor: true },
			});
		});
		expect(chapters.result.current.openChapterContentIds.get(CHAPTER_SERV_ID)).toBe(
			currentCCServId,
		);

		act(() => {
			handleControllerEvent({
				eventType: "textChanged",
				chapterId: CHAPTER_A,
				op: { op: "insert", start: 0, text: "x" },
			});
		});
		expect(chapters.result.current.openChapterContentIds.get(CHAPTER_SERV_ID)).toBeNull();

		// Reopening the same invalidated content version stays null.
		act(() => {
			handleControllerEvent({
				eventType: "chapterOpened",
				chapterId: CHAPTER_A,
				flags: { forEditor: true },
			});
		});
		expect(chapters.result.current.openChapterContentIds.get(CHAPTER_SERV_ID)).toBeNull();

		// Opening a newly synced content version restores the content ID.
		currentCCProvId = CCProvId("cc-prov-2");
		currentCCServId = CCServId("cc-serv-2");
		textSynced = true;
		act(() => {
			handleControllerEvent({
				eventType: "chapterOpened",
				chapterId: CHAPTER_A,
				flags: { forEditor: true },
			});
		});
		expect(chapters.result.current.openChapterContentIds.get(CHAPTER_SERV_ID)).toBe(
			currentCCServId,
		);

		act(() => {
			handleControllerEvent({
				eventType: "chapterClosed",
				chapterId: CHAPTER_A,
			});
		});
		expect(chapters.result.current.openChapterContentIds.has(CHAPTER_SERV_ID)).toBe(false);
	});
});
