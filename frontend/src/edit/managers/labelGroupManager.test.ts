import { act, renderHook } from "@testing-library/react";
import { Effect } from "effect";
import type {
	NovelGetters,
	NovelUserEvent,
	TriggerEvent,
} from "../controller/types/controllerTypes";
import { CCProvId, CProvId, LGProvId } from "../controller/types/idTypes";
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
	chapterContentIdFromServerId: unusedGetter,
	labelIdFromServerId: unusedGetter,
	chapterGetterSlot: unusedGetter,
	labelGroupSlot: unusedGetter,
	autoLabelRunIds: unusedGetter,
	autoLabelRunSlot: unusedGetter,
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
