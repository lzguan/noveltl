import { Effect } from "effect";
import type { Color } from "@/edit/lib/text-model/builtin/colors";
import { generateRandomColor } from "@/edit/lib/text-model/builtin/colors";
import type {
	NovelGetters,
	NovelUserEvent,
	TriggerEvent,
} from "../controller/types/controllerTypes";
import { ActionHappened, CProvId, LGProvId, LProvId } from "../controller/types/idTypes";
import { Prov } from "../controller/types/helperTypes";
import type { useTrackedLabelGroups, LabelGroupView } from "../hooks/useTrackedLabelGroups";
import type { EditorData } from "../hooks/useEditorState";
import { makeStyledLabel } from "./readers";

type LabelGroupTransition = "startLoading" | "finishLoading" | "trackOnly";

function labelGroupView(
	labelGroupName: string,
	color: Color,
	visible: boolean,
	active: boolean,
	status: LabelGroupView["status"],
): LabelGroupView {
	return {
		labelGroup: Prov({ labelGroupName }),
		color,
		visible,
		active,
		status,
	};
}

function withStatus(v: LabelGroupView, status: LabelGroupView["status"]): LabelGroupView {
	return {
		labelGroup: v.labelGroup,
		color: v.color,
		visible: v.visible,
		active: v.active,
		status,
	};
}

function withActive(v: LabelGroupView, active: boolean): LabelGroupView {
	return {
		labelGroup: v.labelGroup,
		color: v.color,
		visible: v.visible,
		active,
		status: v.status,
	};
}

function withVisible(v: LabelGroupView, visible: boolean): LabelGroupView {
	return {
		labelGroup: v.labelGroup,
		color: v.color,
		visible,
		active: v.active,
		status: v.status,
	};
}

export function createLabelGroupManager({
	controllerUserEvent,
	controllerGetters,
	trackedLabelGroups,
	dataRef,
}: {
	controllerUserEvent: (event: NovelUserEvent) => void;
	controllerGetters: NovelGetters;
	trackedLabelGroups: ReturnType<typeof useTrackedLabelGroups>;
	dataRef: { current: EditorData };
}) {
	let activeLabelGroup: LGProvId | null = null;

	function readChapterId(): CProvId | null {
		const current = dataRef.current;
		return current.empty || current.loading ? null : current.chapterId;
	}

	/**
	 * Updates a single label group's tracked status and, when a chapter is
	 * open, synchronises the SegmentManager labels for that group.
	 *
	 * @param labelGroupId - The provisional ID of the label group to update.
	 * @param transition    - What phase the group is entering.
	 *   - `"trackOnly"`:     	ensures the group is tracked (looked up from
	 *                         	controller getters), but does not touch the
	 *                         	open chapter's SegmentManager.
	 *   - `"startLoading"`:   	Removes all of the group's labels from the open
	 * 							chapter's SegmentManager and sets
	 *                         	the tracked status to {@code "loading"}.
	 *   - `"finishLoading"`:  	Reads the freshly-arrived labels from the controller
	 *                       getters, adds them to the SegmentManager in a
	 *                       batch, and sets the tracked status to either
	 *                       {@code "ready"} (on success) or {@code "error"}
	 *                       (on failure).
	 */
	const updateLabelGroupStatus = (
		labelGroupId: LGProvId,
		transition: LabelGroupTransition,
	): Effect.Effect<void> =>
		Effect.gen(function* () {
			const labelGroupExists = yield* Effect.either(
				controllerGetters.labelGroupSlot(labelGroupId),
			);
			if (labelGroupExists._tag === "Left") {
				trackedLabelGroups.removeLabelGroup(labelGroupId);
				return;
			}

			let groupStatus = trackedLabelGroups.labelGroupsRef.current.get(labelGroupId);
			if (!groupStatus) {
				const nameSlot = yield* controllerGetters
					.labelGroupSlot(labelGroupId)
					.pipe(Effect.catchAll(() => Effect.succeed(null)));
				groupStatus = labelGroupView(
					nameSlot?.meta?.labelGroup?.labelGroupName ?? "???",
					generateRandomColor(),
					true,
					false,
					"idle",
				);
				trackedLabelGroups.setLabelGroup(labelGroupId, groupStatus);
			}

			if (transition === "trackOnly") return;

			const current = dataRef.current;
			if (current.empty) return;
			if (current.loading) return;
			const cid = current.chapterId;

			const chapterGetter = yield* controllerGetters
				.chapterGetterSlot(cid)
				.pipe(Effect.catchAll(() => Effect.succeed(null)));
			if (!chapterGetter || chapterGetter.status !== "ready") return;

			if (transition === "startLoading") {
				const sm = current.segmentManager;
				const oldSlot = yield* chapterGetter.data.chapterGetters
					.labelDataSlot(labelGroupId)
					.pipe(Effect.catchAll(() => Effect.succeed(null)));
				if (oldSlot && oldSlot.status === "ready") {
					for (const label of oldSlot.data.labels) {
						try {
							sm.removeLabel(label.labelId);
						} catch {
							/* ignore */
						}
					}
				}
				trackedLabelGroups.setLabelGroup(labelGroupId, withStatus(groupStatus, "loading"));
			} else if (transition === "finishLoading") {
				const sm = current.segmentManager;
				const labelDataSlot = yield* chapterGetter.data.chapterGetters
					.labelDataSlot(labelGroupId)
					.pipe(Effect.catchAll(() => Effect.succeed(null)));

				if (!labelDataSlot || labelDataSlot.status !== "ready") {
					trackedLabelGroups.setLabelGroup(
						labelGroupId,
						withStatus(groupStatus, "error"),
					);
					return;
				}

				const currentGroup =
					trackedLabelGroups.labelGroupsRef.current.get(labelGroupId) ?? groupStatus;
				const labels = labelDataSlot.data.labels;
				const addedIds: LProvId[] = [];
				let batchFailed = false;
				sm.batch(() => {
					for (const label of labels) {
						const styled = makeStyledLabel(
							label,
							currentGroup.color,
							currentGroup.active,
							currentGroup.visible,
						);
						try {
							sm.addLabel(label.labelId, styled);
							addedIds.push(label.labelId);
						} catch {
							batchFailed = true;
							break;
						}
					}
					if (batchFailed) {
						for (const id of addedIds) {
							try {
								sm.removeLabel(id);
							} catch {
								/* ignore */
							}
						}
					}
				});

				if (batchFailed) {
					trackedLabelGroups.setLabelGroup(
						labelGroupId,
						withStatus(groupStatus, "error"),
					);
					return;
				}

				trackedLabelGroups.setLabelGroup(labelGroupId, withStatus(groupStatus, "ready"));
			}
		});

	const updateAllLabelGroupsStatus = (): Effect.Effect<ActionHappened> =>
		Effect.gen(function* () {
			const chapterId = readChapterId();
			if (!chapterId) return ActionHappened(false);
			const chapterSlot = yield* controllerGetters
				.chapterGetterSlot(chapterId)
				.pipe(Effect.catchAll(() => Effect.succeed(null)));
			if (!chapterSlot || chapterSlot.status !== "ready") return ActionHappened(false);
			for (const [
				labelGroupId,
				groupView,
			] of trackedLabelGroups.labelGroupsRef.current.entries()) {
				const labelDataSlot = yield* chapterSlot.data.chapterGetters
					.labelDataSlot(labelGroupId)
					.pipe(Effect.catchAll(() => Effect.succeed(null)));
				if (!labelDataSlot) {
					trackedLabelGroups.setLabelGroup(labelGroupId, withStatus(groupView, "idle"));
				} else {
					trackedLabelGroups.setLabelGroup(
						labelGroupId,
						withStatus(groupView, labelDataSlot.status),
					);
				}
			}
			return ActionHappened(true);
		});

	const updateLabelGroupView = (
		labelGroupId: LGProvId,
		update: Partial<{ visible: boolean; active: boolean; color: Color }>,
	): Effect.Effect<void> =>
		Effect.gen(function* () {
			const entries = trackedLabelGroups.labelGroupsRef.current;
			const group = entries.get(labelGroupId);
			if (!group) return;
			let updated = group;
			if (update.active !== undefined) updated = withActive(updated, update.active);
			if (update.visible !== undefined) updated = withVisible(updated, update.visible);
			if (update.color !== undefined) updated = { ...updated, color: update.color };
			trackedLabelGroups.setLabelGroup(labelGroupId, updated);

			const current = dataRef.current;
			if (current.empty) return;
			if (current.loading) return;
			const cid = current.chapterId;

			const chapterGetter = yield* controllerGetters
				.chapterGetterSlot(cid)
				.pipe(Effect.catchAll(() => Effect.succeed(null)));
			if (!chapterGetter || chapterGetter.status !== "ready") return;

			const labelDataSlot = yield* chapterGetter.data.chapterGetters
				.labelDataSlot(labelGroupId)
				.pipe(Effect.catchAll(() => Effect.succeed(null)));
			if (!labelDataSlot || labelDataSlot.status !== "ready") return;

			const sm = current.segmentManager;
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
						/* ignore */
					}
				}
			});
		});

	function toggleVisibility(labelGroupId: LGProvId) {
		const entries = trackedLabelGroups.labelGroupsRef.current;
		const group = entries.get(labelGroupId);
		const cid = readChapterId();
		if (!group) {
			const nameSlot = Effect.runSync(
				controllerGetters
					.labelGroupSlot(labelGroupId)
					.pipe(Effect.catchAll(() => Effect.succeed(null))),
			);
			trackedLabelGroups.setLabelGroup(
				labelGroupId,
				labelGroupView(
					nameSlot?.meta?.labelGroup?.labelGroupName ?? "???",
					generateRandomColor(),
					true,
					false,
					cid ? "loading" : "idle",
				),
			);
			if (cid) {
				controllerUserEvent({ eventType: "loadLabelData", labelGroupId, chapterId: cid });
			}
			return;
		}
		if (!cid) {
			trackedLabelGroups.setLabelGroup(labelGroupId, withVisible(group, !group.visible));
			return;
		}
		Effect.runSync(
			Effect.gen(function* () {
				yield* updateLabelGroupView(labelGroupId, { visible: !group.visible });
			}),
		);
	}

	function setActive(labelGroupId: LGProvId | null) {
		const current = dataRef.current;
		if (current.empty || current.loading) {
			if (activeLabelGroup) {
				const prev = trackedLabelGroups.labelGroupsRef.current.get(activeLabelGroup);
				if (prev) {
					trackedLabelGroups.setLabelGroup(activeLabelGroup, withActive(prev, false));
				}
			}
			activeLabelGroup = labelGroupId;
			if (labelGroupId) {
				const cur = trackedLabelGroups.labelGroupsRef.current.get(labelGroupId);
				if (cur) {
					trackedLabelGroups.setLabelGroup(labelGroupId, withActive(cur, true));
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
	}

	function addLabelGroup(labelGroupName: string) {
		controllerUserEvent({ eventType: "addLabelGroup", labelGroupName });
	}

	function reloadLabelData(labelGroupId: LGProvId) {
		const cid = readChapterId();
		if (!cid) return;
		controllerUserEvent({ eventType: "loadLabelData", labelGroupId, chapterId: cid });
	}

	function handleControllerEvent(
		_getters: NovelGetters,
		event: TriggerEvent,
	): Effect.Effect<void> {
		return Effect.gen(function* () {
			switch (event.eventType) {
				case "labelGroupAdded":
					yield* updateLabelGroupStatus(event.labelGroup.labelGroupId, "trackOnly");
					{
						const cid = readChapterId();
						if (cid) {
							controllerUserEvent({
								eventType: "loadLabelData",
								labelGroupId: event.labelGroup.labelGroupId,
								chapterId: cid,
							});
						}
					}
					break;
				case "labelDataLoaded":
					if (event.chapterId !== readChapterId()) break;
					yield* updateLabelGroupStatus(event.labelGroupId, "finishLoading");
					break;
				case "labelDataReloading":
					if (event.chapterId !== readChapterId()) break;
					yield* updateLabelGroupStatus(event.labelGroupId, "startLoading");
					break;
				case "chapterOpened":
					if (!event.flags.forEditor) break;
					yield* updateAllLabelGroupsStatus();
					break;
				case "autoLabelRunPromotionFinished":
					break;
			}
		});
	}

	return {
		handleControllerEvent,
		toggleVisibility,
		setActive,
		addLabelGroup,
		reloadLabelData,
		updateLabelGroupStatus,
	};
}
