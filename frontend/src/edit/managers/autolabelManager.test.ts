import { act, renderHook, waitFor } from "@testing-library/react";
import { Effect } from "effect";
import { readAutolabelByIdAutoLabelsAutoLabelIdGet } from "@/api/endpoints/default/default";
import type { AutoLabelMetaWithCid, LabelBase } from "@/api/models";
import type { ChapterGetters, NovelGetters } from "../controller/types/controllerTypes";
import { NotFoundException } from "../controller/types/errors";
import { Prov, type ChapterGetterSlot } from "../controller/types/helperTypes";
import { CCProvId, CCServId, CProvId, CServId } from "../controller/types/idTypes";
import { useAutoLabelPreview } from "../hooks/useAutoLabelPreview";
import type { EditorData } from "../hooks/useEditorState";
import { makeBasicSegmentManager } from "../lib/text-model/core/segmentManager";
import { createAutoLabelManager } from "./autolabelManager";

vi.mock("@/api/endpoints/default/default", () => ({
	readAutolabelByIdAutoLabelsAutoLabelIdGet: vi.fn(),
}));

const readAutoLabel = vi.mocked(readAutolabelByIdAutoLabelsAutoLabelIdGet);

const CHAPTER_PROV_ID = CProvId("chapter-prov-1");
const CHAPTER_SERV_ID = CServId("chapter-serv-1");
const CC_PROV_ID = CCProvId("cc-prov-1");
const CC_SERV_ID = CCServId("cc-serv-1");
const RUN_ID = "run-1";
const AL_ID = "al-1";

const unusedGetter = () => Effect.die("unused getter");

function makeSetup(text = "😀Alice") {
	let textSynced = true;
	const chapterGetters: ChapterGetters = {
		text: () => Effect.succeed(text),
		chapterContentId: () => Effect.succeed(CC_PROV_ID),
		labelDataSlot: () => Effect.fail(new NotFoundException()),
		isDestroyed: () => false,
		isTextSynced: () => textSynced,
	};
	const chapterSlot: ChapterGetterSlot = {
		inFlight: 0,
		status: "ready",
		meta: {
			chapter: Prov({
				chapterId: CHAPTER_PROV_ID,
				chapterNum: 1,
				chapterTitle: "Chapter 1",
				chapterIsPublic: false,
				novelId: "novel-1",
			}),
		},
		data: { chapterGetters },
	};
	const getters: NovelGetters = {
		novel: unusedGetter,
		role: unusedGetter,
		labelGroupIds: unusedGetter,
		chapterIds: unusedGetter,
		chapterIdFromServerId: unusedGetter,
		chapterServerId: (id) =>
			Effect.succeed(id === CHAPTER_PROV_ID ? CHAPTER_SERV_ID : null),
		chapterContentServerId: (id) =>
			Effect.succeed(id === CHAPTER_PROV_ID ? CC_SERV_ID : null),
		chapterContentIdFromServerId: unusedGetter,
		labelIdFromServerId: unusedGetter,
		labelGroupIdFromServerId: unusedGetter,
		labelGroupServerId: unusedGetter,
		chapterGetterSlot: (id) =>
			id === CHAPTER_PROV_ID
				? Effect.succeed(chapterSlot)
				: Effect.fail(new NotFoundException()),
		labelGroupSlot: unusedGetter,
	};
	const dataRef: { current: EditorData } = {
		current: {
			empty: false,
			loading: false,
			chapterId: CHAPTER_PROV_ID,
			chapterContentId: CC_PROV_ID,
			segmentManager: makeBasicSegmentManager(text, []),
			caret: null,
		},
	};
	const previewHook = renderHook(() => useAutoLabelPreview());
	const manager = createAutoLabelManager({
		controllerGetters: getters,
		autoLabelPreview: previewHook.result.current,
		dataRef,
	});
	return {
		getters,
		previewHook,
		manager,
		setTextSynced: (synced: boolean) => {
			textSynced = synced;
		},
	};
}

function makeAutoLabelMeta(
	autoLabelId: string,
	status: AutoLabelMetaWithCid["autoLabelMeta"]["autoLabelStatus"] = "done",
): AutoLabelMetaWithCid {
	return {
		chapterId: CHAPTER_SERV_ID,
		autoLabelMeta: {
			autoLabelId,
			runId: RUN_ID,
			chapterContentId: CC_SERV_ID,
			autoLabelStatus: status,
			autoLabelMessage: null,
			autoLabelLastJobId: null,
		},
	};
}

function makeAutoLabelResponse(autoLabelId: string, labels: LabelBase[]) {
	return {
		status: 200 as const,
		data: {
			autoLabelId,
			runId: RUN_ID,
			chapterContentId: CC_SERV_ID,
			autoLabelStatus: "done" as const,
			autoLabelMessage: null,
			autoLabelLastJobId: null,
			autoLabelData: labels,
		},
		headers: new Headers(),
	};
}

beforeEach(() => {
	readAutoLabel.mockReset();
});

describe("createAutoLabelManager", () => {
	it("loads, converts to UTF-16 offsets, and caches preview spans when enabled", async () => {
		const { previewHook, manager } = makeSetup("😀Alice");
		readAutoLabel.mockResolvedValueOnce(
			makeAutoLabelResponse(AL_ID, [
				{
					labelStart: 1,
					labelEnd: 6,
					labelWord: "Alice",
					labelEntityGroup: "PER",
					labelScore: 0.99,
					labelDirty: false,
				},
			]),
		);

		act(() => {
			manager.setSelectedRun({
				runId: RUN_ID,
				status: "ready",
				autolabels: [makeAutoLabelMeta(AL_ID)],
			});
			manager.setPreviewEnabled(true);
		});

		await waitFor(() => expect(previewHook.result.current.preview).not.toBeNull());
		expect(previewHook.result.current.preview).toEqual([
			expect.objectContaining({
				labelStart: 2,
				labelEnd: 7,
				labelWord: "Alice",
			}),
		]);
		expect(readAutoLabel).toHaveBeenCalledTimes(1);

		// Toggling preview off and back on serves from cache without refetching.
		act(() => {
			manager.setPreviewEnabled(false);
		});
		expect(previewHook.result.current.preview).toBeNull();

		act(() => {
			manager.setPreviewEnabled(true);
		});
		await waitFor(() => expect(previewHook.result.current.preview).not.toBeNull());
		expect(readAutoLabel).toHaveBeenCalledTimes(1);
	});

	it("clears preview and marks the chapter outdated on textChanged", async () => {
		const { getters, previewHook, manager } = makeSetup("Alice");
		readAutoLabel.mockResolvedValueOnce(
			makeAutoLabelResponse(AL_ID, [
				{
					labelStart: 0,
					labelEnd: 5,
					labelWord: "Alice",
					labelEntityGroup: "PER",
					labelScore: 0.9,
					labelDirty: false,
				},
			]),
		);

		act(() => {
			Effect.runSync(
				manager.handleControllerEvent(getters, {
					eventType: "chapterOpened",
					chapterId: CHAPTER_PROV_ID,
					flags: { forEditor: true },
				}),
			);
			manager.setSelectedRun({
				runId: RUN_ID,
				status: "ready",
				autolabels: [makeAutoLabelMeta(AL_ID)],
			});
			manager.setPreviewEnabled(true);
		});

		await waitFor(() => expect(previewHook.result.current.preview).not.toBeNull());
		expect(previewHook.result.current.openChapterContentIds.get(CHAPTER_SERV_ID)).toBe(
			CC_SERV_ID,
		);

		act(() => {
			Effect.runSync(
				manager.handleControllerEvent(getters, {
					eventType: "textChanged",
					chapterId: CHAPTER_PROV_ID,
					op: { op: "insert", start: 0, text: "!" },
				}),
			);
		});

		expect(previewHook.result.current.preview).toBeNull();
		expect(previewHook.result.current.openChapterContentIds.get(CHAPTER_SERV_ID)).toBeNull();
	});

	it("aborts and ignores stale preview responses when switching runs", async () => {
		const { previewHook, manager } = makeSetup("Alice");
		let resolveFirst: (value: ReturnType<typeof makeAutoLabelResponse>) => void = () => {};
		readAutoLabel
			.mockReturnValueOnce(
				new Promise((resolve) => {
					resolveFirst = resolve;
				}),
			)
			.mockResolvedValueOnce(
				makeAutoLabelResponse("al-2", [
					{
						labelStart: 0,
						labelEnd: 5,
						labelWord: "Alice",
						labelEntityGroup: "ORG",
						labelScore: 0.8,
						labelDirty: false,
					},
				]),
			);

		act(() => {
			manager.setPreviewEnabled(true);
			manager.setSelectedRun({
				runId: "run-1",
				status: "ready",
				autolabels: [makeAutoLabelMeta("al-1")],
			});
		});
		expect(previewHook.result.current.loading).toBe(true);

		act(() => {
			manager.setSelectedRun({
				runId: "run-2",
				status: "ready",
				autolabels: [makeAutoLabelMeta("al-2")],
			});
		});

		await waitFor(() =>
			expect(previewHook.result.current.preview).toEqual([
				expect.objectContaining({ labelEntityGroup: "ORG" }),
			]),
		);

		await act(async () => {
			resolveFirst(
				makeAutoLabelResponse("al-1", [
					{
						labelStart: 0,
						labelEnd: 5,
						labelWord: "Alice",
						labelEntityGroup: "PER",
						labelScore: 0.99,
						labelDirty: false,
					},
				]),
			);
		});

		expect(previewHook.result.current.preview).toEqual([
			expect.objectContaining({ labelEntityGroup: "ORG" }),
		]);
	});
});
