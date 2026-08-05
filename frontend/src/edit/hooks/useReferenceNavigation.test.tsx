import { act, renderHook } from "@testing-library/react";
import { Effect } from "effect";
import { describe, expect, it, vi } from "vitest";
import type { NovelGetters } from "../controller/types/controllerTypes";
import { Prov } from "../controller/types/helperTypes";
import { CCProvId, CProvId, LProvId, type ProvChapter } from "../controller/types/idTypes";
import { makeBasicSegmentManager } from "../lib/text-model/core/segmentManager";
import type { StyledLabel } from "../lib/text-model/core/types";
import type { LabelStyle } from "../managers/editorManager";
import type { EditorData } from "./useEditorState";
import { useReferenceNavigation } from "./useReferenceNavigation";

const CHAPTER_ID = CProvId("chapter-prov");
const CONTENT_ID = CCProvId("content-current");
const OLD_CONTENT_ID = CCProvId("content-old");
const LABEL_ID = LProvId("label-prov");
const chapter: ProvChapter = Prov({
	chapterId: CHAPTER_ID,
	chapterNum: 17,
	chapterTitle: "The Gate",
	chapterIsPublic: true,
	novelId: "novel-1",
});
const editorData: EditorData = {
	empty: false,
	loading: false,
	chapterId: CHAPTER_ID,
	chapterContentId: CONTENT_ID,
	segmentManager: makeBasicSegmentManager("0123456789", []),
	caret: null,
};

const unusedGetter = () => Effect.die("unused getter");

function getters(
	contentId: typeof CONTENT_ID,
	labelId: typeof LABEL_ID | null = null,
): NovelGetters {
	return {
		novel: unusedGetter,
		role: unusedGetter,
		labelGroupIds: unusedGetter,
		chapterIds: unusedGetter,
		chapterIdFromServerId: () => Effect.succeed(CHAPTER_ID),
		chapterContentIdFromServerId: () => Effect.succeed(contentId),
		labelIdFromServerId: () => Effect.succeed(labelId),
		chapterGetterSlot: unusedGetter,
		labelGroupSlot: unusedGetter,
		autoLabelRunIds: unusedGetter,
		autoLabelRunSlot: unusedGetter,
	};
}

const reference = {
	type: "textSpan" as const,
	value: {
		chapterId: "chapter-server",
		chapterContentId: "content-server",
		start: 2,
		end: 6,
	},
};

describe("useReferenceNavigation", () => {
	it("opens the chapter and exposes a valid range for the editor", () => {
		const switchChapter = vi.fn();
		const { result } = renderHook(() =>
			useReferenceNavigation({
				chapterList: [chapter],
				controllerGetters: getters(CONTENT_ID),
				editorData,
				switchChapter,
			}),
		);

		act(() => result.current.openTextReference(reference));

		expect(switchChapter).toHaveBeenCalledWith(CHAPTER_ID);
		expect(result.current.highlight).toEqual({ start: 2, end: 6 });
		expect(result.current.notice).toBeNull();
	});

	it("reports the chapter number instead of applying offsets from old content", () => {
		const { result } = renderHook(() =>
			useReferenceNavigation({
				chapterList: [chapter],
				controllerGetters: getters(OLD_CONTENT_ID),
				editorData,
				switchChapter: vi.fn(),
			}),
		);

		act(() => result.current.openTextReference(reference));

		expect(result.current.highlight).toBeNull();
		expect(result.current.notice).toEqual({ kind: "outdated", chapterNum: 17 });
	});

	it("resolves a label server ID to its current text range", () => {
		const segmentManager = makeBasicSegmentManager<
			LabelStyle,
			StyledLabel<LabelStyle>,
			typeof LABEL_ID
		>("0123456789", [
			{
				id: LABEL_ID,
				interval: { start: 3, end: 8 },
				style: [{ color: 0 }, { cursorStatus: "none", visible: true, active: false }],
			},
		]);
		const labelEditorData: EditorData = { ...editorData, segmentManager };
		const { result } = renderHook(() =>
			useReferenceNavigation({
				chapterList: [chapter],
				controllerGetters: getters(CONTENT_ID, LABEL_ID),
				editorData: labelEditorData,
				switchChapter: vi.fn(),
			}),
		);

		act(() =>
			result.current.openTextReference({
				type: "labelRef",
				value: {
					chapterId: "chapter-server",
					chapterContentId: "content-server",
					labelDataId: "label-data-server",
					labelGroupId: "label-group-server",
					labelId: "label-server",
				},
			}),
		);

		expect(result.current.highlight).toEqual({ start: 3, end: 8 });
	});
});
