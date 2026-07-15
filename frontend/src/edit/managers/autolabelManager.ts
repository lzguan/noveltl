import type { RefObject } from "react";
import { Effect } from "effect";
import { UnknownException } from "effect/Cause";
import type { ALRProvId, CCProvId, CProvId, LGProvId } from "../controller/types/idTypes";
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
import type { useAutoLabelPreview } from "../hooks/useAutoLabelPreview";
import type {
	AcquireWorkspaceLock,
	ReleaseWorkspaceLock,
	WorkspaceLockToken,
} from "../hooks/useWorkspaceLock";
import type { EditorMode } from "./editorManager";

/** Coordinates autolabel run state, preview reconciliation, and promotion. */
export type AutoLabelUserEventHandlers = {
	createRun(params: CluenerParams | DoNothingParams, filter: ChapterFilter): void;
	selectRun(runId: ALRProvId): void;
	deselectRun(): void;
	setPreviewEnabled(enabled: boolean): void;
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
	if (runSlot.status !== "ready") {
		return {
			run: { ...runSlot.meta.run, servId: runSlot.meta.servId },
			status: runSlot.status,
		};
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
		run: { ...runSlot.meta.run, servId: runSlot.meta.servId },
		status: "ready" as const,
		overallStatus: deriveOverallStatus(autolabels),
		autolabels,
	};
}

export function createAutoLabelManager({
	controllerUserEvent,
	controllerGetters,
	autoLabels,
	autoLabelPreview,
	dataRef,
	modeRef,
	setMode,
	acquireLock,
	releaseLock,
}: {
	controllerUserEvent(event: NovelUserEvent): void;
	controllerGetters: NovelGetters;
	autoLabels: ReturnType<typeof useAutoLabelState>;
	autoLabelPreview: ReturnType<typeof useAutoLabelPreview>;
	dataRef: RefObject<EditorData>;
	modeRef: RefObject<EditorMode>;
	setMode(mode: EditorMode): void;
	acquireLock: AcquireWorkspaceLock;
	releaseLock: ReleaseWorkspaceLock;
}): AutoLabelManager {
	let modeBeforePromotion: EditorMode | null = null;
	let promotionLockToken: WorkspaceLockToken | null = null;
	let promotingRunId: ALRProvId | null = null;
	const invalidatedContentIds = new Map<CProvId, CCProvId>();

	function releasePromotionLock(): void {
		if (promotionLockToken === null) return;
		const token = promotionLockToken;
		promotionLockToken = null;
		releaseLock(token);
	}

	function finishPromotion(runId: ALRProvId): void {
		if (promotingRunId !== runId) return;
		promotingRunId = null;
		autoLabels.setPromoting(false);
		releasePromotionLock();
		if (modeBeforePromotion !== null) {
			setMode(modeBeforePromotion);
			modeBeforePromotion = null;
		}
	}

	function currentChapterId(): CProvId | null {
		const data = dataRef.current;
		if (data.empty || data.loading) return null;
		return data.chapterId;
	}

	function syncPreview(): Effect.Effect<void> {
		return Effect.gen(function* () {
			if (!autoLabelPreview.enabledRef.current) return;

			const runId = autoLabels.selectedRunIdRef.current;
			const chapterId = currentChapterId();
			if (runId === null || chapterId === null) {
				autoLabelPreview.setPreview(null);
				return;
			}

			const chapterSlot = yield* controllerGetters
				.chapterGetterSlot(chapterId)
				.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
			if (chapterSlot.status !== "ready") {
				autoLabelPreview.setPreview(null);
				return;
			}
			const chapterContentId = yield* chapterSlot.data.chapterGetters
				.chapterContentId()
				.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));

			const invalidatedContentId = invalidatedContentIds.get(chapterId);
			if (invalidatedContentId === chapterContentId) {
				autoLabelPreview.setPreview(null);
				return;
			}
			if (invalidatedContentId !== undefined) invalidatedContentIds.delete(chapterId);

			const runSlot = yield* controllerGetters
				.autoLabelRunSlot(runId)
				.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
			if (runSlot.status !== "ready") {
				autoLabelPreview.setPreview(null);
				return;
			}

			const matching = runSlot.data.autolabels.find(
				(slot) =>
					slot.meta.autoLabel.chapterId === chapterId &&
					slot.meta.autoLabel.autoLabelMeta.chapterContentId === chapterContentId &&
					slot.meta.autoLabel.autoLabelMeta.autoLabelStatus === "done",
			);
			if (!matching) {
				autoLabelPreview.setPreview(null);
				return;
			}

			const autoLabelId = matching.meta.autoLabel.autoLabelMeta.autoLabelId;
			if (matching.status === "ready") {
				autoLabelPreview.setPreview(matching.data.autoLabelData ?? []);
				return;
			}

			autoLabelPreview.setLoading(true);
			if (matching.status === "loading") return;

			controllerUserEvent({
				eventType: "loadAutoLabelData",
				autoLabelId,
				flags: { now: true, forPreview: true },
			});
		}).pipe(
			Effect.catchAll((err) => {
				autoLabelPreview.setPreview(null);
				console.error("Failed to synchronize autolabel preview:", err);
				return Effect.succeed(void 0);
			}),
		);
	}

	function syncPreviewNow(): void {
		void Effect.runPromise(syncPreview()).catch((err) => {
			console.error("Failed to run autolabel preview synchronization:", err);
		});
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

	function refreshSelectedRunAndMatches(
		getters: NovelGetters,
	): Effect.Effect<void, UnknownException> {
		return Effect.gen(function* () {
			const selectedRunId = autoLabels.selectedRunIdRef.current;
			if (selectedRunId !== null) {
				const runSlot = yield* controllerGetters
					.autoLabelRunSlot(selectedRunId)
					.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
				autoLabels.setRun(selectedRunId, makeView(runSlot));
			}
			autoLabels.setChapterMatchMap(
				yield* rebuildChapterMatchMap(autoLabels.runsRef.current, getters),
			);
		});
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
						flags: { now: true },
					});
					yield* syncPreview();
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
					yield* syncPreview();
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
					yield* syncPreview();
					break;
				}

				case "autoLabelRunPromotionFinished": {
					finishPromotion(event.runId);
					break;
				}

				case "chapterOpened": {
					if (!event.flags.forEditor) break;
					yield* refreshSelectedRunAndMatches(getters);
					yield* syncPreview();
					break;
				}

				case "textChanged": {
					yield* refreshSelectedRunAndMatches(getters);
					if (event.chapterId !== currentChapterId()) break;
					autoLabelPreview.setPreview(null);
					const chapterSlot = yield* controllerGetters
						.chapterGetterSlot(event.chapterId)
						.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
					if (chapterSlot.status !== "ready") break;
					invalidatedContentIds.set(
						event.chapterId,
						yield* chapterSlot.data.chapterGetters.chapterContentId(),
					);
					break;
				}

				case "autoLabelDataLoaded": {
					if (event.flags.forPreview) yield* syncPreview();
					break;
				}

				case "errorOccured": {
					if (autoLabels.refreshingRef.current) {
						autoLabels.setRefreshing(false);
					}
					const previewLoadFailed =
						event.from === "requestManager"
							? event.data.some(
									({ request }) => request.variant === "loadAutoLabelData",
								)
							: autoLabelPreview.loadingRef.current;
					if (previewLoadFailed) {
						autoLabelPreview.setPreview(null);
					}
					break;
				}
			}
		}).pipe(
			Effect.catchAll((err) => {
				if (autoLabels.refreshingRef.current) {
					autoLabels.setRefreshing(false);
				}
				autoLabelPreview.setPreview(null);
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
			const runSlot = Effect.runSyncExit(controllerGetters.autoLabelRunSlot(runId));
			if (runSlot._tag === "Failure") {
				console.error("Failed to get run slot for selected run:", runSlot.cause);
				syncPreviewNow();
				return;
			}
			if (runSlot.value.status !== "loading" && runSlot.value.status !== "ready") {
				controllerUserEvent({
					eventType: "reloadAutoLabelRun",
					runId,
					flags: { now: true },
				});
			}
			syncPreviewNow();
		},
		deselectRun() {
			autoLabels.setSelected(null);
			autoLabelPreview.setPreview(null);
		},
		setPreviewEnabled(enabled) {
			autoLabelPreview.setEnabled(enabled);
			if (enabled) syncPreviewNow();
		},
		promote(runId, labelGroupId, filter) {
			const token = acquireLock("Promoting auto labels...");
			if (token === null) return;
			promotionLockToken = token;
			promotingRunId = runId;
			modeBeforePromotion = modeRef.current;

			try {
				autoLabels.setPromoting(true);
				setMode("view");
				controllerUserEvent({
					eventType: "promoteAutoLabelRun",
					runId,
					labelGroupId,
					chapterFilter: filter,
				});
			} catch (error) {
				promotingRunId = null;
				autoLabels.setPromoting(false);
				releasePromotionLock();
				if (modeBeforePromotion !== null) setMode(modeBeforePromotion);
				modeBeforePromotion = null;
				throw error;
			}
		},
		refreshAllRuns() {
			autoLabels.setRefreshing(true);
			if (autoLabelPreview.enabledRef.current) autoLabelPreview.setLoading(true);
			controllerUserEvent({ eventType: "refreshAutoLabelRuns", flags: { now: true } });
		},
		reloadRun(runId) {
			if (
				autoLabelPreview.enabledRef.current &&
				autoLabels.selectedRunIdRef.current === runId
			) {
				autoLabelPreview.setLoading(true);
			}
			controllerUserEvent({ eventType: "reloadAutoLabelRun", runId, flags: { now: true } });
		},
		handleControllerEvent,
	};
}
