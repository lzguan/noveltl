import { Effect } from "effect";
import type { TextOp } from "@/api/models";
import { makeBasicSegmentManager } from "@/components/labeled-text-lib/core/segmentManager";
import type { ColorStyle, ProductStyle } from "@/components/labeled-text-lib/builtin/reducers";
import type {
	NovelGetters,
	NovelUserEvent,
	TriggerEvent,
} from "../controller/types/controllerTypes";
import type { LGProvId } from "../controller/types/idTypes";
import type { LabelOp } from "../controller/types/dataTypes";
import { ChapterLoadingException } from "../controller/types/errors";
import type { EditorData, LoadingPayload } from "../hooks/useEditorState";
import { gatherLabelData, makeStyledLabel } from "./readers";
import type { LabelGroupView } from "../hooks/useTrackedLabelGroups";

export type LabelStyle = ProductStyle<
	[
		ColorStyle,
		{
			cursorStatus: "clicked" | "hovered" | "none";
			visible: boolean;
			active: boolean;
		},
	]
>;

export type EditorMode = "edit" | "view" | "label";

export function createEditorManager({
	controllerUserEvent,
	dataRef,
	modeRef,
	setLoading,
	labelGroupsRef,
}: {
	controllerUserEvent: (event: NovelUserEvent) => void;
	dataRef: { current: EditorData };
	modeRef: { current: EditorMode };
	setLoading: (val: LoadingPayload) => void;
	labelGroupsRef: { current: Map<LGProvId, LabelGroupView> };
}) {
	function handleControllerEvent(
		novelGetters: NovelGetters,
		event: TriggerEvent,
	): Effect.Effect<void> {
		return Effect.gen(function* () {
			switch (event.eventType) {
				case "chapterOpened": {
					if (!event.flags.forEditor) break;
					const done = yield* Effect.either(
						Effect.gen(function* () {
							const chapterGetter = yield* novelGetters.chapterGetterSlot(
								event.chapterId,
							);
							if (chapterGetter.status !== "ready") {
								return yield* Effect.fail(
									new ChapterLoadingException({ chapterId: event.chapterId }),
								);
							}
							const result = yield* gatherLabelData(
								chapterGetter,
								labelGroupsRef.current,
							);
							return {
								text: yield* chapterGetter.data.chapterGetters.text(),
								labelData: result.labelData,
								couldNotLoad: result.couldNotLoad,
							};
						}),
					);
					if (done._tag === "Left") break;
					const { text, labelData, couldNotLoad } = done.right;
					const flatLabelData = Array.from(labelData.values()).flat();

					setLoading({
						loading: false,
						segmentManager: makeBasicSegmentManager(text, flatLabelData),
						chapterId: event.chapterId,
					});
					if (couldNotLoad.length > 0) {
						console.warn(
							`Failed to load label data for label groups: ${couldNotLoad.join(", ")}`,
						);
					}
					break;
				}
				case "textChanged": {
					const current = dataRef.current;
					if (current.loading) break;
					if (event.chapterId !== current.chapterId) break;
					const sm = current.segmentManager;
					if (event.op.op === "insert") {
						sm.insertTextAt(event.op.start, event.op.text);
					} else {
						sm.deleteTextAt(event.op.start, event.op.text.length);
					}
					break;
				}
				case "labelChanged": {
					const current = dataRef.current;
					if (current.loading) break;
					if (event.op.chapterId !== current.chapterId) break;
					const groupStatus = labelGroupsRef.current.get(event.op.labelGroupId);
					if (!groupStatus) break;
					const sm = current.segmentManager;
					if (event.op.op === "add") {
						sm.addLabel(
							event.op.labelId,
							makeStyledLabel(
								{
									labelId: event.op.labelId,
									labelStart: event.op.startPos,
									labelEnd: event.op.endPos,
								},
								groupStatus.color,
								groupStatus.active,
								groupStatus.visible,
							),
						);
					} else if (event.op.op === "delete") {
						sm.removeLabel(event.op.labelId);
					} else if (event.op.op === "update") {
						sm.updateLabel(
							event.op.labelId,
							makeStyledLabel(
								{
									labelId: event.op.labelId,
									labelStart: event.op.startPos,
									labelEnd: event.op.endPos,
								},
								groupStatus.color,
								groupStatus.active,
								groupStatus.visible,
							),
						);
					}
					break;
				}
			}
		});
	}

	function textOp(op: TextOp) {
		if (modeRef.current !== "edit") return;
		const current = dataRef.current;
		if (current.loading) return;
		controllerUserEvent({ eventType: "textOp", op, chapterId: current.chapterId });
	}

	function labelOp(op: LabelOp, labelGroupId: LGProvId) {
		if (modeRef.current !== "label") return;
		const current = dataRef.current;
		if (current.loading) return;
		controllerUserEvent({
			eventType: "labelOp",
			op,
			labelGroupId,
			chapterId: current.chapterId,
		});
	}

	return { handleControllerEvent, textOp, labelOp };
}
