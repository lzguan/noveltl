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
import type { useTrackedLabelGroups } from "../hooks/useTrackedLabelGroups";
import type { EditorData } from "../hooks/useEditorState";

type LabelGroupTransition = "startLoading" | "finishLoading" | "trackOnly";

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
				groupStatus = {
					labelGroup: Prov({
						labelGroupName: nameSlot?.meta?.labelGroup?.labelGroupName ?? "???",
					}),
					color: generateRandomColor(),
					visible: true,
					status: "idle",
				};
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
				trackedLabelGroups.setLabelGroup(labelGroupId, {
					...groupStatus,
					status: "loading",
				});
			} else if (transition === "finishLoading") {
				const sm = current.segmentManager;
				const labelDataSlot = yield* chapterGetter.data.chapterGetters
					.labelDataSlot(labelGroupId)
					.pipe(Effect.catchAll(() => Effect.succeed(null)));

				if (!labelDataSlot || labelDataSlot.status !== "ready") {
					trackedLabelGroups.setLabelGroup(labelGroupId, {
						...groupStatus,
						status: "error",
					});
					return;
				}

				const currentGroup =
					trackedLabelGroups.labelGroupsRef.current.get(labelGroupId) ?? groupStatus;
				const labels = labelDataSlot.data.labels;
				const addedIds: LProvId[] = [];
				let batchFailed = false;
				sm.batch(() => {
					for (const label of labels) {
						const styled = {
							interval: { start: label.labelStart, end: label.labelEnd },
							style: [
								{ color: currentGroup.color },
								{
									cursorStatus: "none" as const,
									active:
										labelGroupId ===
										trackedLabelGroups.activeLabelGroupIdRef.current,
									visible: currentGroup.visible,
								},
							],
							id: label.labelId,
						} as const;

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
					trackedLabelGroups.setLabelGroup(labelGroupId, {
						...groupStatus,
						status: "error",
					});
					return;
				}

				trackedLabelGroups.setLabelGroup(labelGroupId, {
					...groupStatus,
					status: "ready",
				});
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
					trackedLabelGroups.setLabelGroup(labelGroupId, {
						...groupView,
						status: "idle",
					});
				} else {
					trackedLabelGroups.setLabelGroup(labelGroupId, {
						...groupView,
						status: labelDataSlot.status,
					});
				}
			}
			return ActionHappened(true);
		});

	/**
	 * Updates a single label group's tracked status.
	 *
	 * @param labelGroupId
	 * @param update
	 * @returns
	 */
	const updateLabelGroupView = (
		labelGroupId: LGProvId,
		update: Partial<{ visible: boolean; color: Color }>,
	): Effect.Effect<void> =>
		Effect.gen(function* () {
			const entries = trackedLabelGroups.labelGroupsRef.current;
			const group = entries.get(labelGroupId);
			if (!group) return;
			let updated = group;
			if (update.visible !== undefined) updated = { ...updated, visible: update.visible };
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
					const styled = {
						interval: { start: label.labelStart, end: label.labelEnd },
						style: [
							{ color: updated.color },
							{
								cursorStatus: "none" as const,
								active:
									labelGroupId ===
									trackedLabelGroups.activeLabelGroupIdRef.current,
								visible: updated.visible,
							},
						],
						id: label.labelId,
					} as const;
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
			trackedLabelGroups.setLabelGroup(labelGroupId, {
				labelGroup: Prov({
					labelGroupName: nameSlot?.meta?.labelGroup?.labelGroupName ?? "???",
				}),
				color: generateRandomColor(),
				visible: true,
				status: cid ? "loading" : "idle",
			});
			if (cid) {
				controllerUserEvent({ eventType: "loadLabelData", labelGroupId, chapterId: cid });
			}
			return;
		}
		if (!cid) {
			trackedLabelGroups.setLabelGroup(labelGroupId, { ...group, visible: !group.visible });
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
		const curActive = trackedLabelGroups.activeLabelGroupIdRef.current;
		if (current.empty || current.loading) {
			trackedLabelGroups.setActive(labelGroupId);
			return;
		}
		trackedLabelGroups.setActive(labelGroupId);
		Effect.runSync(
			Effect.gen(function* () {
				if (curActive) {
					yield* updateLabelGroupView(curActive, {});
				}
				if (labelGroupId) {
					yield* updateLabelGroupView(labelGroupId, {});
				}
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
