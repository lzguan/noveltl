import { act, renderHook } from "@testing-library/react";
import { Effect } from "effect";
import { makeBasicSegmentManager } from "@/edit/lib/text-model/core/segmentManager";
import type { StyledLabel } from "@/edit/lib/text-model/core/types";
import type { NovelGetters, TriggerEvent } from "../controller/types/controllerTypes";
import { Prov } from "../controller/types/helperTypes";
import { CCProvId, CCServId, CProvId, CServId, type LProvId } from "../controller/types/idTypes";
import type { LabelStyle } from "../managers/editorManager";
import {
	createOpenChapterContentsSubscriber,
	deriveAutoLabelPreviewTarget,
	useOpenChapterContents,
} from "./useOpenChapterContents";

const CHAPTER_A = CProvId("chapter-a");
const CHAPTER_SERV_ID = CServId("chapter-serv-a");
const unusedGetter = () => Effect.die("unused getter");

describe("useOpenChapterContents", () => {
	it("tracks synced content IDs across open, text edits, reopen, and close", () => {
		let currentCCProvId = CCProvId("cc-prov-1");
		let currentCCServId: CCServId | null = CCServId("cc-serv-1");
		let textSynced = true;

		const getters: NovelGetters = {
			novel: unusedGetter,
			role: unusedGetter,
			labelGroupIds: unusedGetter,
			chapterIds: unusedGetter,
			chapterIdFromServerId: unusedGetter,
			chapterServerId: (id) => Effect.succeed(id === CHAPTER_A ? CHAPTER_SERV_ID : null),
			chapterContentServerId: (id) =>
				Effect.succeed(id === CHAPTER_A ? currentCCServId : null),
			chapterContentIdFromServerId: unusedGetter,
			labelIdFromServerId: unusedGetter,
			labelGroupIdFromServerId: unusedGetter,
			labelGroupServerId: unusedGetter,
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
			labelGroupSlot: unusedGetter,
		};

		const { result } = renderHook(() => useOpenChapterContents());
		const handleEvent = createOpenChapterContentsSubscriber(result.current);
		const send = (event: TriggerEvent) => {
			act(() => {
				Effect.runSync(handleEvent(getters, event));
			});
		};

		send({ eventType: "chapterOpened", chapterId: CHAPTER_A, flags: { forEditor: true } });
		expect(result.current.openChapterContentIds.get(CHAPTER_SERV_ID)).toBe(currentCCServId);

		send({
			eventType: "textChanged",
			chapterId: CHAPTER_A,
			op: { op: "insert", start: 0, text: "x" },
		});
		expect(result.current.openChapterContentIds.get(CHAPTER_SERV_ID)).toBeNull();

		// Reopening the same invalidated content version stays null.
		send({ eventType: "chapterOpened", chapterId: CHAPTER_A, flags: { forEditor: true } });
		expect(result.current.openChapterContentIds.get(CHAPTER_SERV_ID)).toBeNull();

		// textSynced restores the newly synced content ID without needing chapterOpened.
		currentCCProvId = CCProvId("cc-prov-2");
		currentCCServId = CCServId("cc-serv-2");
		textSynced = true;
		send({ eventType: "textSynced", chapterId: CHAPTER_A });
		expect(result.current.openChapterContentIds.get(CHAPTER_SERV_ID)).toBe(currentCCServId);

		send({ eventType: "chapterClosed", chapterId: CHAPTER_A });
		expect(result.current.openChapterContentIds.has(CHAPTER_SERV_ID)).toBe(false);
	});
});

describe("deriveAutoLabelPreviewTarget", () => {
	const getters = {
		chapterServerId: (id: CProvId) => Effect.succeed(id === CHAPTER_A ? CHAPTER_SERV_ID : null),
	};

	it("returns null when editor is empty, loading, unmapped, or dirty", () => {
		const sm = makeBasicSegmentManager<LabelStyle, StyledLabel<LabelStyle>, LProvId>(
			"hello",
			[],
		);
		const ccId = CCProvId("cc-1");
		const syncedMap = new Map<string, string | null>([[CHAPTER_SERV_ID, "cc-serv-1"]]);
		const dirtyMap = new Map<string, string | null>([[CHAPTER_SERV_ID, null]]);

		expect(deriveAutoLabelPreviewTarget({ empty: true }, getters, syncedMap)).toBeNull();
		expect(
			deriveAutoLabelPreviewTarget({ empty: false, loading: true }, getters, syncedMap),
		).toBeNull();
		expect(
			deriveAutoLabelPreviewTarget(
				{
					empty: false,
					loading: false,
					segmentManager: sm,
					chapterId: CProvId("unmapped"),
					chapterContentId: ccId,
					caret: null,
				},
				getters,
				syncedMap,
			),
		).toBeNull();
		expect(
			deriveAutoLabelPreviewTarget(
				{
					empty: false,
					loading: false,
					segmentManager: sm,
					chapterId: CHAPTER_A,
					chapterContentId: ccId,
					caret: null,
				},
				getters,
				dirtyMap,
			),
		).toBeNull();
	});

	it("returns the chapter server ID, synced content ID, and current text when synced", () => {
		const sm = makeBasicSegmentManager<LabelStyle, StyledLabel<LabelStyle>, LProvId>(
			"hello world",
			[],
		);
		const syncedMap = new Map<string, string | null>([[CHAPTER_SERV_ID, "cc-serv-1"]]);

		expect(
			deriveAutoLabelPreviewTarget(
				{
					empty: false,
					loading: false,
					segmentManager: sm,
					chapterId: CHAPTER_A,
					chapterContentId: CCProvId("cc-1"),
					caret: null,
				},
				getters,
				syncedMap,
			),
		).toEqual({
			chapterId: CHAPTER_SERV_ID,
			chapterContentId: "cc-serv-1",
			text: "hello world",
		});
	});
});
