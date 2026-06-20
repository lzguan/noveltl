import type { TextOp } from "@/api/models";
import type {
	NovelGetters,
	NovelUserEvent,
	SubscriberFn,
	TriggerEvent,
} from "../controller/types/controllerTypes";
import type { CProvId, LGProvId, LProvId } from "../controller/types/idTypes";
import type { IDLabelOp } from "../controller/types/dataTypes";
import type { Caret } from "@/components/labeled-text-lib/react/DynamicLabeledText";
import type { ColorStyle, ProductStyle } from "@/components/labeled-text-lib/builtin/reducers";
import {
	makeBasicSegmentManager,
	type ManagedLabel,
	type SegmentManager,
} from "@/components/labeled-text-lib/core/segmentManager";
import type { StyledLabel } from "@/components/labeled-text-lib/core/types";
import { Effect } from "effect";
import { ChapterLoadingException } from "../controller/types/errors";
import { buildPubSub } from "../utils/pubsub";
import { generateRandomColor, type Color } from "@/components/labeled-text-lib/builtin/colors";

export type LabelStyle = ProductStyle<
	[
		ColorStyle,
		{
			cursorStatus: "clicked" | "hovered" | "none";
		} & ({ visible: true; active: true } | { visible: boolean; active: false }),
	]
>;

export type EditorMode = "edit" | "view" | "label";

export type EditorTriggers =
	| { eventType: "loadingStart" }
	| { eventType: "modeChange"; mode: EditorMode }
	| { eventType: "hoverPosChange"; pos: number | null }
	| { eventType: "caretChange"; caret: Caret | null }
	| { eventType: "chapterSwitch"; chapterId: CProvId }
	| { eventType: "textOp"; op: TextOp }
	| { eventType: "labelOp"; op: IDLabelOp }
	| { eventType: "errorOccured"; error: unknown };

/**
 * Placeholder getters type for Editor manager. Will be updated as needed.
 */
type EditorManagerGetters = {
	isLoading: () => boolean;
	mode: () => EditorMode;
};

/**
 * Interface for the Editor manager. Stores all data that is relevant to rendering the editor. Acts as a bridge from any component that is relevant to rendering the editor to the controller. Specifically, stores the following:
 * - Currently open chapter
 * - Label groups/label datas
 * - Segments (see labeled text library)
 */
export interface EditorManager {
	/**
	 * Respond to trigger events emitted by the controller.
	 */
	handleTriggerEvent: SubscriberFn<NovelGetters, TriggerEvent>;
	/**
	 * Send a message to the controller to switch the currently open chapter.
	 */
	switchChapter(chapterId: CProvId): void;
	/**
	 * Send a text operation text op to the controller, or reject if the mode is not "edit".
	 */
	textOp(op: TextOp): void;
	/**
	 * Send a label operation label op to the controller, along with the target label group id. Reject if the mode is not "label".
	 */
	labelOp(op: IDLabelOp): void;
	/**
	 * Switch the editor mode between edit, view, and label.
	 */
	switchMode(mode: EditorMode): void;
	/**
	 * Set the position of the mouse hover. If null is passed, it means the mouse is not hovering over any text.
	 */
	hoverPos(pos: number | null): void;
	/**
	 * Set the position of the caret.
	 */
	setCaret(caret: Caret | null): void;
	/**
	 * Subscribe to changes in the editor manager's state.
	 */
	subscribe: (callback: SubscriberFn<EditorManagerGetters, EditorTriggers>) => () => void;
	/**
	 * Toggle visibility of a label group. If the label group is currently visible, it becomes hidden, and vice versa.
	 */
	toggleVisibility: (labelGroupId: LGProvId) => void;
	/**
	 * Set active label group. There is at most one active label group at a time. The active property is purely a ui state to emphasize one label group among potentially many visible label groups, and has no effect on the actual data or operations of the label groups.
	 */
	setActive: (labelGroupId: LGProvId | null) => void;
	/**
	 * Get the current state of the editor manager.
	 */
	getters: EditorManagerGetters;
}

type MyManagedLabel = ManagedLabel<LabelStyle, StyledLabel<LabelStyle>, LProvId>;

function makeStyledLabel(
	label: { labelId: LProvId; labelStart: number; labelEnd: number },
	color: Color,
	active: boolean,
	visible: boolean,
): MyManagedLabel {
	return {
		interval: {
			start: label.labelStart,
			end: label.labelEnd,
		},
		style: [
			{ color },
			{
				cursorStatus: "none",
				...(() =>
					active ? { active: true, visible: true } : { active: false, visible })(),
			},
		],
		id: label.labelId,
	};
}

export function buildEditorManager(
	{
		segmentManager,
		chapterId,
	}:
		| {
				segmentManager: SegmentManager<LabelStyle, StyledLabel<LabelStyle>, LProvId>;
				chapterId: CProvId;
		  }
		| { segmentManager: null; chapterId: null },
	setSMC: ({
		segmentManager,
		chapterId,
	}:
		| {
				segmentManager: SegmentManager<LabelStyle, StyledLabel<LabelStyle>, LProvId>;
				chapterId: CProvId;
		  }
		| { segmentManager: null; chapterId: null }) => void,
	controllerUserEvent: (event: NovelUserEvent) => void,
	controllerGetters: NovelGetters,
): EditorManager {
	let loading = false;
	let mode: EditorMode = "view" as EditorMode;
	let curHoverPos: number | null = null;
	let caret: Caret | null = null;

	let visibleLabelGroups = new Map<
		LGProvId,
		{
			color: Color;
			visible: boolean;
			active: boolean;
			status: "ready" | "error" | "loading";
		}
	>(); // color here placeholder for now, will add to db later
	let activeLabelGroup: LGProvId | null = null;
	const { subscribe, raiseTriggerEvent } = buildPubSub<EditorManagerGetters, EditorTriggers>();
	const getters: EditorManagerGetters = {
		isLoading: () => loading,
		mode: () => mode,
	};
	const handleTriggerEvent: SubscriberFn<NovelGetters, TriggerEvent> = (novelGetters, event) => {
		switch (event.eventType) {
			case "chapterOpened": {
				if (!event.flags.forEditor) {
					break;
				}
				const couldNotLoad: LGProvId[] = [];
				const done = Effect.runSyncExit(
					Effect.gen(function* () {
						const chapterGetter = yield* novelGetters.chapterGetterSlot(
							event.chapterId,
						);
						if (chapterGetter.status !== "ready") {
							return yield* Effect.fail(
								new ChapterLoadingException({ chapterId: event.chapterId }),
							);
						}
						const labelData = new Map<LGProvId, readonly MyManagedLabel[]>();

						for (const [labelGroupId, groupStatus] of visibleLabelGroups) {
							const labelDataSlot = yield* chapterGetter.data.chapterGetters
								.labelDataSlot(labelGroupId)
								.pipe(
									Effect.catchAll(() =>
										Effect.succeed({ status: "error" as "error" }),
									),
								); // casting :( is what it is
							if (labelDataSlot.status !== "ready") {
								couldNotLoad.push(labelGroupId);
								continue;
							}
							labelData.set(
								labelGroupId,
								labelDataSlot.data.labels.map((label) =>
									makeStyledLabel(
										label,
										groupStatus.color,
										activeLabelGroup === labelGroupId,
										groupStatus.visible,
									),
								),
							);
						}
						return { text: yield* chapterGetter.data.chapterGetters.text(), labelData };
					}),
				);
				if (done._tag === "Failure") {
					Effect.runSync(
						raiseTriggerEvent(getters, {
							eventType: "errorOccured",
							error: new Error(`Failed to load chapter: ${done.cause}`),
						}),
					);
					break;
				}
				const { text, labelData } = done.value;
				const flatLabelData: MyManagedLabel[] = [];

				for (const labels of labelData.values()) {
					flatLabelData.push(...labels);
				}

				setSMC({
					segmentManager: makeBasicSegmentManager<
						LabelStyle,
						StyledLabel<LabelStyle>,
						LProvId
					>(text, flatLabelData),
					chapterId: event.chapterId,
				});
				loading = false;
				Effect.runSync(
					raiseTriggerEvent(getters, {
						eventType: "chapterSwitch",
						chapterId: event.chapterId,
					}),
				);
				if (couldNotLoad.length > 0) {
					Effect.runSync(
						raiseTriggerEvent(getters, {
							eventType: "errorOccured",
							error: new Error(
								`Failed to load label data for label groups: ${couldNotLoad.join(", ")}`,
							),
						}),
					);
				}
				break;
			}
			case "labelChanged": {
				if (event.op.chapterId !== chapterId) {
					break;
				}
				const groupStatus = visibleLabelGroups.get(event.op.labelGroupId);
				if (!groupStatus) {
					break;
				}
				if (event.op.op === "add") {
					const label = makeStyledLabel(
						{
							labelId: event.op.labelId,
							labelStart: event.op.startPos,
							labelEnd: event.op.endPos,
						},
						groupStatus.color,
						activeLabelGroup === event.op.labelGroupId,
						groupStatus.visible,
					);
					segmentManager.addLabel(event.op.labelId, label);
					break;
				} else if (event.op.op === "delete") {
					segmentManager.removeLabel(event.op.labelId);
					break;
				} else if (event.op.op === "update") {
					const label = makeStyledLabel(
						{
							labelId: event.op.labelId,
							labelStart: event.op.startPos,
							labelEnd: event.op.endPos,
						},
						groupStatus.color,
						activeLabelGroup === event.op.labelGroupId,
						groupStatus.visible,
					);
					segmentManager.updateLabel(event.op.labelId, label);
					break;
				}
				break;
			}
			case "textChanged": {
				if (event.chapterId !== chapterId) {
					break;
				}
				if (event.op.op === "insert") {
					segmentManager.insertTextAt(event.op.start, event.op.text);
				} else if (event.op.op === "delete") {
					segmentManager.deleteTextAt(event.op.start, event.op.text.length);
				}
				break;
			}
		}
	};
	const switchChapter = (chapterId: CProvId) => {
		loading = true;
		setSMC({ segmentManager: null, chapterId: null });
		Effect.runSync(raiseTriggerEvent(getters, { eventType: "loadingStart" }));
		controllerUserEvent({
			eventType: "openChapter",
			chapterId,
			eagerLabelGroupIds: Array.from(visibleLabelGroups.keys()),
			flags: { now: true, forEditor: true, fromCached: true },
		});
	};
	const textOp = (op: TextOp) => {
		if (mode !== "edit") {
			Effect.runSync(
				raiseTriggerEvent(getters, {
					eventType: "errorOccured",
					error: new Error("Cannot perform text operations in non-edit mode"),
				}),
			);
			return;
		}
		if (!chapterId) {
			Effect.runSync(
				raiseTriggerEvent(getters, {
					eventType: "errorOccured",
					error: new Error("No chapter is currently open"),
				}),
			);
			return;
		}
		controllerUserEvent({ eventType: "textOp", op, chapterId: chapterId });
	};
	const labelOp = (op: IDLabelOp) => {
		if (mode !== "label") {
			Effect.runSync(
				raiseTriggerEvent(getters, {
					eventType: "errorOccured",
					error: new Error("Cannot perform label operations in non-label mode"),
				}),
			);
			return;
		}
		if (!chapterId) {
			Effect.runSync(
				raiseTriggerEvent(getters, {
					eventType: "errorOccured",
					error: new Error("No chapter is currently open"),
				}),
			);
			return;
		}
		if (chapterId !== op.chapterId) {
			Effect.runSync(
				raiseTriggerEvent(getters, {
					eventType: "errorOccured",
					error: new Error(
						"Label operation chapterId does not match currently open chapterId",
					),
				}),
			);
			return;
		}
		controllerUserEvent({ eventType: "labelOp", op, labelGroupId: op.labelGroupId, chapterId });
	};

	const switchMode = (newMode: EditorMode) => {
		mode = newMode;
		Effect.runSync(raiseTriggerEvent(getters, { eventType: "modeChange", mode: newMode }));
	};
	const hoverPos = (pos: number | null) => {
		curHoverPos = pos;
		Effect.runSync(raiseTriggerEvent(getters, { eventType: "hoverPosChange", pos }));
	};
	const setCaret = (newCaret: Caret | null) => {
		caret = newCaret;
		Effect.runSync(raiseTriggerEvent(getters, { eventType: "caretChange", caret: newCaret }));
	};
	const toggleVisibility = (labelGroupId: LGProvId) => {
		if (!chapterId) {
			if (visibleLabelGroups.has(labelGroupId)) {
			} else {
				visibleLabelGroups.set(labelGroupId, {
					color: generateRandomColor(),
					visible: true,
					active: false,
					status: "ready",
				});
			}
			return;
		}
		if (visibleLabelGroups.has(labelGroupId)) {
			Effect.runSyncExit(
				Effect.gen(function* () {
					const chapterGetter = yield* controllerGetters.chapterGetterSlot(chapterId);
					if (chapterGetter.status !== "ready") {
						controllerUserEvent({
							eventType: "loadLabelData",
							labelGroupId,
							chapterId,
						});
					}
				}),
			);
		}
	};
}
