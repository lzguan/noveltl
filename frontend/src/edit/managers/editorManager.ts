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
import { UnknownException } from "effect/Cause";

// parts of this file are vibe coded, look through carefully later.

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
	| { eventType: "loadingStart" } // start loading a chapter (either on chapter switch or on initial load)
	| { eventType: "labelGroupLoadingStart"; labelGroupId: LGProvId; chapterId: CProvId } // start loading label data for a label group in a chapter
	| {
			eventType: "labelGroupLoadingEnd";
			labelGroupId: LGProvId;
			chapterId: CProvId;
	  } // finish loading label data for a label group in a chapter on success
	| { eventType: "modeChange"; mode: EditorMode } // on successful change editor mode
	| { eventType: "hoverPosChange"; pos: number | null } // on successful change mouse hover position
	| { eventType: "caretChange"; caret: Caret | null } // on successful change caret position
	| { eventType: "chapterSwitch"; chapterId: CProvId } // on successful change currently open chapter
	| { eventType: "chapterAdded"; chapterId: CProvId } // on successful chapter creation
	| { eventType: "textOp"; op: TextOp } // on successful text operation
	| { eventType: "labelOp"; op: IDLabelOp } // on successful label operation
	| { eventType: "visibilityChange"; labelGroupId: LGProvId; chapterId: CProvId } // on successful toggle visibility of a label group
	| { eventType: "labelGroupsChanged" } // on label group list mutation (added, deleted, etc.)
	| { eventType: "errorOccured"; error: unknown }; // on any error

export type LabelGroupEntry = {
	id: LGProvId;
	name: string;
	color: Color;
	visible: boolean;
	active: boolean;
	status: "ready" | "error" | "loading" | "idle";
};

/**
 * Placeholder getters type for Editor manager. Will be updated as needed.
 */
type EditorManagerGetters = {
	isLoading: () => boolean;
	mode: () => EditorMode;
	labelGroups: () => LabelGroupEntry[];
	segmentManager: () => SegmentManager<LabelStyle, StyledLabel<LabelStyle>, LProvId> | null;
	currentChapterId: () => CProvId | null;
	chapterIds: () => readonly CProvId[];
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
	 * Send a message to the controller to create a new chapter.
	 */
	addChapter: (chapterNum: number, chapterTitle: string, chapterIsPublic: boolean) => void;
	/**
	 * Send a message to the controller to create a new label group.
	 */
	addLabelGroup: (labelGroupName: string) => void;
	/**
	 * Send a message to the controller to reload label data for a label group in the currently open chapter. No-op if no chapter is open.
	 */
	reloadLabelData: (labelGroupId: LGProvId) => void;
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

export type EditorSMC = {
	segmentManager: SegmentManager<LabelStyle, StyledLabel<LabelStyle>, LProvId> | null;
	chapterId: CProvId | null;
};

export function buildEditorManager(
	smcRef: { current: EditorSMC },
	setSmc: (smc: EditorSMC) => void,
	controllerUserEvent: (event: NovelUserEvent) => void,
	controllerGetters: NovelGetters,
): EditorManager {
	let loading = false;
	let mode: EditorMode = "view" as EditorMode;
	let prevHoverPos: number | null = null;
	let prevCaret: Caret | null = null;

	const trackedLabelGroups = new Map<
		LGProvId,
		{
			name: string;
			color: Color;
			visible: boolean;
			active: boolean;
			status: "ready" | "error" | "loading" | "idle";
		}
	>(); // color here placeholder for now, will add to db later
	let activeLabelGroup: LGProvId | null = null;

	const chapterIdList: CProvId[] = [];
	const { subscribe, raiseTriggerEvent } = buildPubSub<EditorManagerGetters, EditorTriggers>();
	const getters: EditorManagerGetters = {
		isLoading: () => loading,
		mode: () => mode,
		segmentManager: () => smcRef.current.segmentManager,
		currentChapterId: () => smcRef.current.chapterId,
		chapterIds: () => {
			if (chapterIdList.length === 0) {
				Effect.runSync(
					controllerGetters.chapterIds().pipe(
						Effect.map((ids) => {
							chapterIdList.length = 0;
							chapterIdList.push(...ids);
						}),
					),
				);
			}
			return chapterIdList;
		},
		labelGroups: () =>
			Array.from(trackedLabelGroups.entries()).map(([id, g]) => ({
				id,
				name: g.name,
				color: g.color,
				visible: g.visible,
				active: g.active,
				status: g.status,
			})),
	};

	type LabelGroupTransition = "startLoading" | "finishLoading" | "trackOnly";

	/**
	 * Central helper for label group lifecycle in the editor.
	 *
	 * - trackOnly: ensures the group is tracked (create entry with defaults if not).
	 * - startLoading: removes all existing labels for this group from the segment
	 *   manager, updates tracking to "loading", and raises labelGroupLoadingStart.
	 * - finishLoading: queries the controller for all labels for this group, adds
	 *   them to the segment manager in a batch (rolling back on any failure),
	 *   updates tracking to "ready", and raises labelGroupLoadingEnd / error.
	 */
	const updateLabelGroupStatus = (labelGroupId: LGProvId, transition: LabelGroupTransition) =>
		Effect.gen(function* () {
			// Validate the label group still exists in controller state.
			const labelGroupExists = yield* Effect.either(
				controllerGetters.labelGroupSlot(labelGroupId),
			);
			if (labelGroupExists._tag === "Left") {
				trackedLabelGroups.delete(labelGroupId);
				return;
			}

			// Ensure a tracking entry is present (trackOnly is done here).
			let groupStatus = trackedLabelGroups.get(labelGroupId);
			if (!groupStatus) {
				const nameSlot = yield* controllerGetters
					.labelGroupSlot(labelGroupId)
					.pipe(Effect.catchAll(() => Effect.succeed(null)));
				groupStatus = {
					name: nameSlot?.meta?.labelGroup?.labelGroupName ?? "???",
					color: generateRandomColor(),
					visible: true,
					active: false,
					status: "idle" as const,
				};
				trackedLabelGroups.set(labelGroupId, groupStatus);
			}

			if (transition === "trackOnly") {
				return;
			}

			// All transitions below require an open chapter.
			const cid = smcRef.current.chapterId;
			if (!cid) {
				return;
			}

			const chapterGetter = yield* controllerGetters
				.chapterGetterSlot(cid)
				.pipe(Effect.catchAll(() => Effect.succeed(null)));
			if (!chapterGetter || chapterGetter.status !== "ready") {
				return;
			}

			if (transition === "startLoading") {
				const sm = smcRef.current.segmentManager;
				if (!sm) return;
				// Remove old labels for this group from the segment manager.
				const oldSlot = yield* chapterGetter.data.chapterGetters
					.labelDataSlot(labelGroupId)
					.pipe(Effect.catchAll(() => Effect.succeed(null)));
				if (oldSlot && oldSlot.status === "ready") {
					for (const label of oldSlot.data.labels) {
						try {
							sm.removeLabel(label.labelId);
						} catch {
							// Label may have already been removed individually.
						}
					}
				}

				trackedLabelGroups.set(labelGroupId, { ...groupStatus, status: "loading" });

				yield* raiseTriggerEvent(getters, {
					eventType: "labelGroupLoadingStart",
					labelGroupId,
					chapterId: cid,
				});
			} else if (transition === "finishLoading") {
				const smFinish = smcRef.current.segmentManager;
				if (!smFinish) return;
				const labelDataSlot = yield* chapterGetter.data.chapterGetters
					.labelDataSlot(labelGroupId)
					.pipe(Effect.catchAll(() => Effect.succeed(null)));

				if (!labelDataSlot || labelDataSlot.status !== "ready") {
					trackedLabelGroups.set(labelGroupId, { ...groupStatus, status: "error" });
					yield* raiseTriggerEvent(getters, {
						eventType: "errorOccured",
						error: new UnknownException(
							`Failed to load label data for label group ${labelGroupId}`,
						),
					});
					return;
				}

				const labels = labelDataSlot.data.labels;
				const currentGroup = trackedLabelGroups.get(labelGroupId) ?? groupStatus;
				const addedIds: LProvId[] = [];
				let batchFailed = false;
				smFinish.batch(() => {
					for (const label of labels) {
						const styled = makeStyledLabel(
							label,
							currentGroup.color,
							currentGroup.active,
							currentGroup.visible,
						);
						try {
							smFinish.addLabel(label.labelId, styled);
							addedIds.push(label.labelId);
						} catch {
							batchFailed = true;
							break;
						}
					}
					if (batchFailed) {
						for (const id of addedIds) {
							try {
								smFinish.removeLabel(id);
							} catch {
								// Already gone — ignore.
							}
						}
					}
				});

				if (batchFailed) {
					trackedLabelGroups.set(labelGroupId, { ...groupStatus, status: "error" });
					yield* raiseTriggerEvent(getters, {
						eventType: "errorOccured",
						error: new UnknownException(
							`Failed to add labels for label group ${labelGroupId}`,
						),
					});
					return;
				}

				trackedLabelGroups.set(labelGroupId, { ...groupStatus, status: "ready" });
				yield* raiseTriggerEvent(getters, {
					eventType: "labelGroupLoadingEnd",
					labelGroupId,
					chapterId: cid,
				});
			}
		});

	const updateLabelGroupView = (
		labelGroupId: LGProvId,
		update: Partial<{ visible: boolean; active: boolean; color: Color }>,
	): Effect.Effect<void> =>
		Effect.gen(function* () {
			const group = trackedLabelGroups.get(labelGroupId);
			if (!group) {
				return;
			}
			const updated = { ...group, ...update };
			trackedLabelGroups.set(labelGroupId, updated);

			const cid = smcRef.current.chapterId;
			if (!cid) {
				return;
			}
			const chapterGetter = yield* controllerGetters
				.chapterGetterSlot(cid)
				.pipe(Effect.catchAll(() => Effect.succeed(null)));
			if (!chapterGetter || chapterGetter.status !== "ready") {
				return;
			}
			const labelDataSlot = yield* chapterGetter.data.chapterGetters
				.labelDataSlot(labelGroupId)
				.pipe(Effect.catchAll(() => Effect.succeed(null)));
			if (!labelDataSlot || labelDataSlot.status !== "ready") {
				return;
			}
			const sm = smcRef.current.segmentManager;
			if (!sm) return;
			sm.batch(() => {
				for (const label of labelDataSlot.data.labels) {
					const styled = makeStyledLabel(
						label,
						updated.color,
						updated.active,
						updated.visible,
					);
					try {
						sm.updateLabel(label.labelId, styled);
					} catch {
						// Label may not be in SM yet — ignore.
					}
				}
			});
		});

	const handleTriggerEvent: SubscriberFn<NovelGetters, TriggerEvent> = (novelGetters, event) =>
		Effect.gen(function* () {
			switch (event.eventType) {
				case "chapterOpened": {
					if (!event.flags.forEditor) {
						break;
					}
					const couldNotLoad: LGProvId[] = [];
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
							const labelData = new Map<LGProvId, readonly MyManagedLabel[]>();

							for (const [labelGroupId, groupStatus] of trackedLabelGroups) {
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
							return {
								text: yield* chapterGetter.data.chapterGetters.text(),
								labelData,
							};
						}).pipe(
							Effect.tapError((err) =>
								raiseTriggerEvent(getters, {
									eventType: "errorOccured",
									error: new Error(
										`Failed to load chapter: ${err instanceof Error ? err : String(err)}`,
									),
								}),
							),
						),
					); // casting :( is what it is
					if (done._tag === "Left") {
						yield* raiseTriggerEvent(getters, {
							eventType: "errorOccured",
							error: new Error(`Failed to load chapter: ${done.left}`),
						});
						break;
					}
					const { text, labelData } = done.right;
					const flatLabelData: MyManagedLabel[] = [];

					for (const labels of labelData.values()) {
						flatLabelData.push(...labels);
					}

				setSmc({
					segmentManager: makeBasicSegmentManager<
						LabelStyle,
						StyledLabel<LabelStyle>,
						LProvId
					>(text, flatLabelData),
					chapterId: event.chapterId,
				});
					loading = false;
					yield* raiseTriggerEvent(getters, {
						eventType: "chapterSwitch",
						chapterId: event.chapterId,
					});
					if (couldNotLoad.length > 0) {
						yield* raiseTriggerEvent(getters, {
							eventType: "errorOccured",
							error: new Error(
								`Failed to load label data for label groups: ${couldNotLoad.join(", ")}`,
							),
						});
					}
					break;
				}
				case "labelChanged": {
					if (event.op.chapterId !== smcRef.current.chapterId) {
						break;
					}
					const groupStatus = trackedLabelGroups.get(event.op.labelGroupId);
					if (!groupStatus) {
						break;
					}
					const sm = smcRef.current.segmentManager;
					if (!sm) break;
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
						sm.addLabel(event.op.labelId, label);
						break;
					} else if (event.op.op === "delete") {
						sm.removeLabel(event.op.labelId);
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
						sm.updateLabel(event.op.labelId, label);
						break;
					}
					break;
				}
				case "textChanged": {
					if (event.chapterId !== smcRef.current.chapterId) {
						break;
					}
					const sm = smcRef.current.segmentManager;
					if (!sm) break;
					if (event.op.op === "insert") {
						sm.insertTextAt(event.op.start, event.op.text);
					} else if (event.op.op === "delete") {
						sm.deleteTextAt(event.op.start, event.op.text.length);
					}
					break;
				}
				case "labelGroupAdded": {
					yield* updateLabelGroupStatus(event.labelGroup.labelGroupId, "trackOnly");
					yield* raiseTriggerEvent(getters, { eventType: "labelGroupsChanged" });
					const cid = smcRef.current.chapterId;
					if (cid) {
						controllerUserEvent({
							eventType: "loadLabelData",
							labelGroupId: event.labelGroup.labelGroupId,
							chapterId: cid,
						});
					}
					break;
				}
				case "chapterAdded": {
					console.time("chapterAdded handler");
					chapterIdList.length = 0;
					const ids = Effect.runSync(controllerGetters.chapterIds());
					chapterIdList.push(...ids);
					yield* raiseTriggerEvent(getters, {
						eventType: "chapterAdded",
						chapterId: event.chapter.chapterId,
					});
					console.timeEnd("chapterAdded handler");
					break;
				}
				case "labelDataLoaded": {
					if (event.chapterId !== smcRef.current.chapterId) {
						break;
					}
					yield* updateLabelGroupStatus(event.labelGroupId, "finishLoading");
					break;
				}
				case "labelDataReloading": {
					if (event.chapterId !== smcRef.current.chapterId) {
						break;
					}
					yield* updateLabelGroupStatus(event.labelGroupId, "startLoading");
					break;
				}
			}
		});
	const switchChapter = (newChapterId: CProvId) => {
		loading = true;
		setSmc({ segmentManager: null, chapterId: null });
		Effect.runSync(raiseTriggerEvent(getters, { eventType: "loadingStart" }));
		controllerUserEvent({
			eventType: "openChapter",
			chapterId: newChapterId,
			eagerLabelGroupIds: Array.from(trackedLabelGroups.keys()),
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
		const cid = smcRef.current.chapterId;
		if (!cid) {
			Effect.runSync(
				raiseTriggerEvent(getters, {
					eventType: "errorOccured",
					error: new Error("No chapter is currently open"),
				}),
			);
			return;
		}
		controllerUserEvent({ eventType: "textOp", op, chapterId: cid });
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
		const cid = smcRef.current.chapterId;
		if (!cid) {
			Effect.runSync(
				raiseTriggerEvent(getters, {
					eventType: "errorOccured",
					error: new Error("No chapter is currently open"),
				}),
			);
			return;
		}
		if (cid !== op.chapterId) {
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
		controllerUserEvent({ eventType: "labelOp", op, labelGroupId: op.labelGroupId, chapterId: cid });
	};

	const switchMode = (newMode: EditorMode) => {
		mode = newMode;
		Effect.runSync(raiseTriggerEvent(getters, { eventType: "modeChange", mode: newMode }));
	};
	const hoverPos = (pos: number | null) => {
		prevHoverPos = pos;
		Effect.runSync(raiseTriggerEvent(getters, { eventType: "hoverPosChange", pos }));
	};
	const setCaret = (newCaret: Caret | null) => {
		const oldPos = prevCaret?.focus ?? null;
		const pos = newCaret?.focus ?? null;
		const sm = smcRef.current.segmentManager;
		if (oldPos !== null && sm) {
			const hoverIds = prevHoverPos !== null ? sm.labelsAt(prevHoverPos) : [];
			for (const id of sm.labelsAt(oldPos)) {
				try {
					const label = sm.getLabel(id);
					const newStatus: "hovered" | "none" = hoverIds.includes(id)
						? "hovered"
						: "none";
					sm.updateLabel(id, {
						...label,
						style: [
							label.style[0],
							{ ...label.style[1], cursorStatus: newStatus },
						] as typeof label.style,
					} as typeof label);
				} catch {
					// Label may have been removed.
				}
			}
		}
		prevCaret = newCaret;
		if (pos !== null && sm) {
			for (const id of sm.labelsAt(pos)) {
				try {
					const label = sm.getLabel(id);
					sm.updateLabel(id, {
						...label,
						style: [
							label.style[0],
							{ ...label.style[1], cursorStatus: "clicked" as const },
						] as typeof label.style,
					} as typeof label);
				} catch {
					// Label may have been removed.
				}
			}
		}
		Effect.runSync(raiseTriggerEvent(getters, { eventType: "caretChange", caret: newCaret }));
	};
	const toggleVisibility = (labelGroupId: LGProvId) => {
		const group = trackedLabelGroups.get(labelGroupId);
		const cid = smcRef.current.chapterId;
		if (!group) {
			const nameSlot = Effect.runSync(
				controllerGetters.labelGroupSlot(labelGroupId).pipe(
					Effect.catchAll(() => Effect.succeed(null)),
				),
			);
			trackedLabelGroups.set(labelGroupId, {
				name: nameSlot?.meta?.labelGroup?.labelGroupName ?? "???",
				color: generateRandomColor(),
				visible: true,
				active: false,
				status: cid ? "loading" : "idle",
			});
			if (cid) {
				controllerUserEvent({
					eventType: "loadLabelData",
					labelGroupId,
					chapterId: cid,
				});
			}
			return;
		}
		if (!cid) {
			trackedLabelGroups.set(labelGroupId, { ...group, visible: !group.visible });
			return;
		}
		Effect.runSync(
			Effect.gen(function* () {
				yield* updateLabelGroupView(labelGroupId, { visible: !group.visible });
				yield* raiseTriggerEvent(getters, {
					eventType: "visibilityChange",
					labelGroupId,
					chapterId: cid,
				});
			}),
		);
	};

	const setActive = (labelGroupId: LGProvId | null) => {
		if (!smcRef.current.chapterId) {
			const prevActive = activeLabelGroup ? trackedLabelGroups.get(activeLabelGroup) : null;
			if (prevActive && activeLabelGroup) {
				trackedLabelGroups.set(activeLabelGroup, { ...prevActive, active: false });
			}
			activeLabelGroup = labelGroupId;
			if (labelGroupId) {
				const newActive = trackedLabelGroups.get(labelGroupId);
				if (newActive) {
					trackedLabelGroups.set(labelGroupId, { ...newActive, active: true });
				}
			}
			return;
		}
		Effect.runSync(
			Effect.gen(function* () {
				if (activeLabelGroup) {
					yield* updateLabelGroupView(activeLabelGroup, { active: false });
				}
				if (labelGroupId) {
					yield* updateLabelGroupView(labelGroupId, { active: true });
				}
				activeLabelGroup = labelGroupId;
			}),
		);
	};

	const addChapter = (chapterNum: number, chapterTitle: string, chapterIsPublic: boolean) => {
		controllerUserEvent({
			eventType: "addChapter",
			chapterNum,
			chapterTitle,
			chapterIsPublic,
		});
	};

	const addLabelGroup = (labelGroupName: string) => {
		controllerUserEvent({
			eventType: "addLabelGroup",
			labelGroupName,
		});
	};

	const reloadLabelData = (labelGroupId: LGProvId) => {
		const cid = smcRef.current.chapterId;
		if (!cid) return;
		controllerUserEvent({
			eventType: "loadLabelData",
			labelGroupId,
			chapterId: cid,
		});
	};

	// Seed trackedLabelGroups from existing controller label groups
	Effect.runSync(
		Effect.gen(function* () {
			const ids = yield* controllerGetters.labelGroupIds();
			for (const id of ids) {
				yield* updateLabelGroupStatus(id, "trackOnly");
			}
		}),
	);

	return {
		handleTriggerEvent,
		switchChapter,
		textOp,
		labelOp,
		switchMode,
		hoverPos,
		setCaret,
		subscribe,
		toggleVisibility,
		setActive,
		addChapter,
		addLabelGroup,
		reloadLabelData,
		getters,
	};
}
