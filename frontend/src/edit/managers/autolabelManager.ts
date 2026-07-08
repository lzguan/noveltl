import type { RefObject } from "react";
import { Effect } from "effect";
import { UnknownException } from "effect/Cause";
import type { ALRProvId, CProvId, LGProvId } from "../controller/types/idTypes";
import type { AutoLabelRunGetterSlot } from "../controller/types/helperTypes";
import { Prov } from "../controller/types/helperTypes";
import type {
	ChapterFilter,
	NovelGetters,
	NovelUserEvent,
	TriggerEvent,
} from "../controller/types/controllerTypes";
import type { CluenerParams, DoNothingParams } from "@/api/models";
import type {
	AutoLabelRunView,
	AutoLabelView,
	ChapterMatchStatus,
	useAutoLabelState,
} from "../hooks/useAutoLabelState";
import type { EditorData } from "../hooks/useEditorState";
import type { EditorMode } from "./editorManager";

/**
 * Select a run: set selectedRunId, fire reloadAutoLabelRun.
 * On autoLabelRunReloaded: if chapter open ∧ matching autolabel ∧ data not loaded → fire loadAutoLabelData.
 */
export type AutoLabelUserEventHandlers = {
	createRun(params: CluenerParams | DoNothingParams, filter: ChapterFilter): void;
	selectRun(runId: ALRProvId): void;
	deselectRun(): void;
	promote(runId: ALRProvId, labelGroupId: LGProvId, filter: ChapterFilter): void;
	refreshAllRuns(): void;
	reloadRun(runId: ALRProvId): void;
};

export type AutoLabelManager = AutoLabelUserEventHandlers & {
	handleControllerEvent(getters: NovelGetters, event: TriggerEvent): Effect.Effect<void>;
};

function deriveOverallStatus(
	autolabels: readonly AutoLabelView[],
): AutoLabelView["autoLabelStatus"] {
	if (autolabels.some((al) => al.autoLabelStatus === "processing")) return "processing";
	if (autolabels.some((al) => al.autoLabelStatus === "pending")) return "pending";
	if (autolabels.length > 0 && autolabels.every((al) => al.autoLabelStatus === "failed")) {
		return "failed";
	}
	return "done";
}

function makeView(runSlot: AutoLabelRunGetterSlot): AutoLabelRunView {
	if (runSlot.status !== "ready" || !runSlot.data) {
		return { run: runSlot.meta.run, status: runSlot.status } as AutoLabelRunView;
	}
	const autolabels: AutoLabelView[] = runSlot.data.autolabels.map((alSlot) =>
		Prov({
			autoLabelId: alSlot.meta.autoLabel.autoLabelMeta.autoLabelId,
			autoLabelLastJobId: alSlot.meta.autoLabel.autoLabelMeta.autoLabelLastJobId,
			autoLabelMessage: alSlot.meta.autoLabel.autoLabelMeta.autoLabelMessage,
			autoLabelStatus: alSlot.meta.autoLabel.autoLabelMeta.autoLabelStatus,
			chapterId: alSlot.meta.autoLabel.chapterId,
			chapterContentId: alSlot.meta.autoLabel.autoLabelMeta.chapterContentId,
			runId: alSlot.meta.autoLabel.autoLabelMeta.runId,
		}),
	);
	return {
		run: runSlot.meta.run,
		status: "ready" as const,
		overallStatus: deriveOverallStatus(autolabels),
		autolabels,
	};
}

export function createAutoLabelManager({
	controllerUserEvent,
	controllerGetters,
	autoLabels,
	dataRef,
	modeRef,
	setMode,
}: {
	controllerUserEvent(event: NovelUserEvent): void;
	controllerGetters: NovelGetters;
	autoLabels: ReturnType<typeof useAutoLabelState>;
	dataRef: RefObject<EditorData>;
	modeRef: RefObject<EditorMode>;
	setMode(mode: EditorMode): void;
}): AutoLabelManager {
	let modeBeforePromotion: EditorMode | null = null;

	function currentChapterId(): CProvId | null {
		const data = dataRef.current;
		if (data.empty || data.loading) return null;
		return data.chapterId;
	}

	function rebuildChapterMatchMap(
		runs: readonly AutoLabelRunView[],
		getters: NovelGetters,
	): Effect.Effect<Map<ALRProvId, Map<CProvId, ChapterMatchStatus>>> {
		return Effect.gen(function* () {
			const result = new Map<ALRProvId, Map<CProvId, ChapterMatchStatus>>();
			for (const run of runs) {
				if (run.status !== "ready") continue;
				const runMap = new Map<CProvId, ChapterMatchStatus>();
				for (const al of run.autolabels) {
					const slot = yield* getters
						.chapterGetterSlot(al.chapterId)
						.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
					if (slot.status !== "ready") continue;
					const currentCC = yield* slot.data.chapterGetters
						.chapterContentId()
						.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
					runMap.set(
						al.chapterId,
						currentCC === al.chapterContentId ? "match" : "outdated",
					);
				}
				result.set(run.run.runId, runMap);
			}
			return result;
		}).pipe(Effect.catchAll(() => Effect.succeed(new Map())));
	}

	function handleControllerEvent(
		getters: NovelGetters,
		event: TriggerEvent,
	): Effect.Effect<void> {
		return Effect.gen(function* () {
			switch (event.eventType) {
				case "autoLabelRunCreated": {
					const runSlot = yield* controllerGetters
						.autoLabelRunSlot(event.run.runId)
						.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
					const view = makeView(runSlot);
					autoLabels.addRun(view);
					autoLabels.setSelected(event.run.runId);
					controllerUserEvent({
						eventType: "reloadAutoLabelRun",
						runId: event.run.runId,
					});
					break;
				}

				case "autoLabelRunsRefreshed": {
					const runIds = yield* controllerGetters
						.autoLabelRunIds()
						.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
					const views: AutoLabelRunView[] = [];
					for (const runId of runIds) {
						const runSlot = yield* controllerGetters
							.autoLabelRunSlot(runId)
							.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
						views.push(makeView(runSlot));
					}
					autoLabels.setRunsList(views);
					autoLabels.setRefreshing(false);
					autoLabels.setChapterMatchMap(yield* rebuildChapterMatchMap(views, getters));
					break;
				}

				case "autoLabelRunReloaded": {
					const runSlot = yield* controllerGetters
						.autoLabelRunSlot(event.runId)
						.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
					const view = makeView(runSlot);
					autoLabels.setRun(event.runId, view);
					const matchMap = yield* rebuildChapterMatchMap(
						autoLabels.runsRef.current,
						getters,
					);
					autoLabels.setChapterMatchMap(matchMap);

					if (autoLabels.selectedRunIdRef.current !== event.runId) break;
					const chId = currentChapterId();
					if (!chId || view.status !== "ready") break;
					if (matchMap.get(event.runId)?.get(chId) !== "match") break;
					const matching = view.autolabels.find(
						(al) => al.chapterId === chId && al.autoLabelStatus === "done",
					);
					if (!matching) break;
					controllerUserEvent({
						eventType: "loadAutoLabelData",
						autoLabelId: matching.autoLabelId,
					});
					break;
				}

				case "autoLabelRunPromoted": {
					autoLabels.setPromoting(false);
					if (modeBeforePromotion !== null) {
						setMode(modeBeforePromotion);
						modeBeforePromotion = null;
					}
					break;
				}

				case "textChanged":
				case "chapterOpened": {
					const selectedRunId = autoLabels.selectedRunIdRef.current;
					let selectedView: AutoLabelRunView | null = null;
					if (selectedRunId !== null) {
						const runSlot = yield* controllerGetters
							.autoLabelRunSlot(selectedRunId)
							.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
						selectedView = makeView(runSlot);
						autoLabels.setRun(selectedRunId, selectedView);
					}

					const matchMap = yield* rebuildChapterMatchMap(
						autoLabels.runsRef.current,
						getters,
					);
					autoLabels.setChapterMatchMap(matchMap);

					const chId = currentChapterId();
					if (
						selectedRunId === null ||
						!chId ||
						selectedView === null ||
						selectedView.status !== "ready"
					) {
						break;
					}
					if (matchMap.get(selectedRunId)?.get(chId) !== "match") break;
					const matching = selectedView.autolabels.find(
						(al) => al.chapterId === chId && al.autoLabelStatus === "done",
					);
					if (!matching) break;
					controllerUserEvent({
						eventType: "loadAutoLabelData",
						autoLabelId: matching.autoLabelId,
					});
					break;
				}

				case "errorOccured": {
					if (autoLabels.promotingRef.current) {
						autoLabels.setPromoting(false);
						if (modeBeforePromotion !== null) {
							setMode(modeBeforePromotion);
							modeBeforePromotion = null;
						}
					}
					if (autoLabels.refreshingRef.current) {
						autoLabels.setRefreshing(false);
					}
					break;
				}
			}
		}).pipe(
			Effect.catchAll((err) => {
				if (autoLabels.promotingRef.current) {
					autoLabels.setPromoting(false);
					if (modeBeforePromotion !== null) {
						setMode(modeBeforePromotion);
						modeBeforePromotion = null;
					}
				}
				if (autoLabels.refreshingRef.current) {
					autoLabels.setRefreshing(false);
				}
				console.error("Error in autolabel manager:", err);
				return Effect.succeed(void 0);
			}),
		);
	}

	return {
		createRun(params, filter) {
			controllerUserEvent({ eventType: "createAutoLabelRun", params, chapterFilter: filter });
		},
		selectRun(runId) {
			autoLabels.setSelected(runId);
			controllerUserEvent({ eventType: "reloadAutoLabelRun", runId });
		},
		deselectRun() {
			autoLabels.setSelected(null);
		},
		promote(runId, labelGroupId, filter) {
			modeBeforePromotion = modeRef.current;
			autoLabels.setPromoting(true);
			setMode("view");
			controllerUserEvent({
				eventType: "promoteAutoLabelRun",
				runId,
				labelGroupId,
				chapterFilter: filter,
			});
		},
		refreshAllRuns() {
			autoLabels.setRefreshing(true);
			controllerUserEvent({ eventType: "refreshAutoLabelRuns" });
		},
		reloadRun(runId) {
			controllerUserEvent({ eventType: "reloadAutoLabelRun", runId });
		},
		handleControllerEvent,
	};
}
