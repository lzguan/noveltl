import { act, renderHook } from "@testing-library/react";
import { Effect } from "effect";
import type {
	ChapterGetters,
	NovelGetters,
	NovelUserEvent,
	TriggerEvent,
} from "../controller/types/controllerTypes";
import { NotFoundException } from "../controller/types/errors";
import type { ChapterGetterSlot, LabelDataSlot } from "../controller/types/helperTypes";
import { Prov } from "../controller/types/helperTypes";
import { CCProvId, CProvId, LDProvId, LGProvId, LGServId } from "../controller/types/idTypes";
import { useEditorState } from "../hooks/useEditorState";
import { useTrackedLabelGroups } from "../hooks/useTrackedLabelGroups";
import { makeBasicSegmentManager } from "../lib/text-model/core/segmentManager";
import { createLabelGroupManager } from "./labelGroupManager";

const CHAPTER_ID = CProvId("chapter-a");
const CHAPTER_CONTENT_ID = CCProvId("chapter-content-a");
const LABEL_GROUP_ID = LGProvId("label-group-a");

const unusedGetter = () => Effect.die("unused getter");
const getters: NovelGetters = {
	novel: unusedGetter,
	role: unusedGetter,
	labelGroupIds: unusedGetter,
	chapterIds: unusedGetter,
	chapterIdFromServerId: unusedGetter,
	chapterServerId: unusedGetter,
	chapterContentServerId: unusedGetter,
	chapterContentIdFromServerId: unusedGetter,
	labelIdFromServerId: unusedGetter,
	labelGroupIdFromServerId: unusedGetter,
	labelGroupServerId: unusedGetter,
	chapterGetterSlot: unusedGetter,
	labelGroupSlot: unusedGetter,
};

describe("createLabelGroupManager", () => {
	it("requeues label data when the controller marks it outdated", () => {
		const editor = renderHook(() => useEditorState());
		const trackedLabelGroups = renderHook(() => useTrackedLabelGroups());
		const controllerEvents: NovelUserEvent[] = [];

		act(() => {
			editor.result.current.setLoading({
				empty: false,
				loading: false,
				chapterId: CHAPTER_ID,
				chapterContentId: CHAPTER_CONTENT_ID,
				segmentManager: makeBasicSegmentManager("Alice", []),
			});
		});

		const manager = createLabelGroupManager({
			controllerUserEvent: (event) => {
				controllerEvents.push(event);
			},
			controllerGetters: getters,
			trackedLabelGroups: trackedLabelGroups.result.current,
			dataRef: editor.result.current.dataRef,
		});
		const event: TriggerEvent = {
			eventType: "labelDataOutdated",
			chapterId: CHAPTER_ID,
			labelGroupId: LABEL_GROUP_ID,
		};

		Effect.runSync(manager.handleControllerEvent(getters, event));

		expect(controllerEvents).toEqual([
			{
				eventType: "loadLabelData",
				chapterId: CHAPTER_ID,
				labelGroupId: LABEL_GROUP_ID,
			},
		]);
	});
});

function labelDataSlot(): LabelDataSlot {
	return {
		inFlight: 0,
		status: "idle",
		meta: {
			labelData: Prov({
				labelDataId: LDProvId("label-data"),
				chapterContentId: CHAPTER_CONTENT_ID,
				labelGroupId: LABEL_GROUP_ID,
			}),
		},
	};
}

function chapterSlot(
	chapterId: CProvId,
	{ hasGroup, destroyed = false }: { hasGroup: boolean; destroyed?: boolean },
): ChapterGetterSlot {
	const chapterGetters: ChapterGetters = {
		text: unusedGetter,
		chapterContentId: unusedGetter,
		labelDataSlot: () =>
			hasGroup ? Effect.succeed(labelDataSlot()) : Effect.fail(new NotFoundException()),
		isDestroyed: () => destroyed,
		isTextSynced: () => true,
	};
	return {
		inFlight: 0,
		status: "ready",
		meta: {
			chapter: Prov({
				chapterNum: 1,
				chapterTitle: "title",
				chapterIsPublic: false,
				novelId: "novel",
				chapterId,
			}),
		},
		data: { chapterGetters },
	};
}

describe("reloadPromotedLabelGroup", () => {
	const loaded = CProvId("loaded");
	const withoutGroup = CProvId("without-group");
	const loading = CProvId("loading");
	const destroyed = CProvId("destroyed");
	const slots = new Map<CProvId, ChapterGetterSlot | "loading">([
		[loaded, chapterSlot(loaded, { hasGroup: true })],
		[withoutGroup, chapterSlot(withoutGroup, { hasGroup: false })],
		[loading, "loading"],
		[destroyed, chapterSlot(destroyed, { hasGroup: true, destroyed: true })],
		[CHAPTER_ID, chapterSlot(CHAPTER_ID, { hasGroup: true })],
	]);
	const reloadGetters: NovelGetters = {
		...getters,
		chapterIds: () => Effect.succeed([...slots.keys()]),
		labelGroupIdFromServerId: (servId) =>
			Effect.succeed(servId === LGServId("group-serv") ? LABEL_GROUP_ID : null),
		chapterGetterSlot: (chapterId) => {
			const slot = slots.get(chapterId);
			if (slot === undefined) return Effect.fail(new NotFoundException());
			if (slot === "loading") {
				return Effect.succeed({
					inFlight: 1,
					status: "loading",
					meta: chapterSlot(chapterId, { hasGroup: true }).meta,
				});
			}
			return Effect.succeed(slot);
		},
	};

	function setup() {
		const editor = renderHook(() => useEditorState());
		const trackedLabelGroups = renderHook(() => useTrackedLabelGroups());
		const controllerEvents: NovelUserEvent[] = [];
		act(() => {
			editor.result.current.setLoading({
				empty: false,
				loading: false,
				chapterId: CHAPTER_ID,
				chapterContentId: CHAPTER_CONTENT_ID,
				segmentManager: makeBasicSegmentManager("Alice", []),
			});
		});
		const manager = createLabelGroupManager({
			controllerUserEvent: (event) => {
				controllerEvents.push(event);
			},
			controllerGetters: reloadGetters,
			trackedLabelGroups: trackedLabelGroups.result.current,
			dataRef: editor.result.current.dataRef,
		});
		return { manager, controllerEvents };
	}

	it("reloads the group in loaded chapters that have it, the open chapter first", () => {
		const { manager, controllerEvents } = setup();

		manager.reloadPromotedLabelGroup("group-serv");

		expect(controllerEvents).toEqual([
			{ eventType: "loadLabelData", labelGroupId: LABEL_GROUP_ID, chapterId: CHAPTER_ID },
			{ eventType: "loadLabelData", labelGroupId: LABEL_GROUP_ID, chapterId: loaded },
		]);
	});

	it("ignores groups this page does not know", () => {
		const { manager, controllerEvents } = setup();

		manager.reloadPromotedLabelGroup("other-serv");

		expect(controllerEvents).toEqual([]);
	});
});
