import { useCallback, useEffect, useEffectEvent, useRef, useState } from "react";
import {
	createAutolabelsAutoLabelsPost,
	readAutoLabelRunsAutoLabelRunsGet,
	readAutoLabelsByRunAutoLabelRunsRunIdAutoLabelsGet,
} from "@/api/endpoints/default/default";
import type { AutoLabelRun, CluenerParams, DoNothingParams } from "@/api/models";
import {
	applyRunAutoLabels,
	applyRunCreated,
	applyRunError,
	applyRunLoading,
	applyRunsList,
	applySelectRun,
	EMPTY_RUNS_STATE,
	isRunActive,
	sameRunsState,
	toSelectedAutoLabelRun,
	type AutoLabelRunsState,
	type ChapterFilter,
	type SelectedAutoLabelRun,
} from "./autoLabelRunsState";

export const AUTO_LABEL_RUN_POLL_INTERVAL_MS = 2000;
export const MAX_IDLE_POLL_INTERVAL_MS = 15_000;
const MAX_POLL_BACKOFF_MS = 30_000;

export type CreateAutoLabelRunResult =
	| { readonly ok: true; readonly run: AutoLabelRun }
	| { readonly ok: false; readonly reason: "badRequest" | "notFound" | "failed" };

type LoopActions = {
	refreshAll(): void;
	reloadRun(runId: string): void;
	wake(): void;
};

export function useAutoLabelRuns({
	novelId,
	onSelectedRunChange,
}: {
	novelId: string | null;
	onSelectedRunChange?: (selection: SelectedAutoLabelRun) => void;
}) {
	const [state, setState] = useState<AutoLabelRunsState>(EMPTY_RUNS_STATE);
	const [refreshing, setRefreshing] = useState(false);
	const [creating, setCreating] = useState(false);
	const stateRef = useRef<AutoLabelRunsState>(EMPTY_RUNS_STATE);
	const actionsRef = useRef<LoopActions | null>(null);
	const generationRef = useRef(0);

	const commitState = useCallback((next: AutoLabelRunsState): boolean => {
		if (sameRunsState(stateRef.current, next)) return false;
		stateRef.current = next;
		setState(next);
		return true;
	}, []);

	const notifySelectedFromEffect = useEffectEvent((selection: SelectedAutoLabelRun) => {
		onSelectedRunChange?.(selection);
	});

	useEffect(() => {
		if (novelId === null) return;

		generationRef.current += 1;
		const abort = new AbortController();
		let refreshListPending = true;
		let manualRefresh = false;
		const pendingRunIds = new Set<string>();
		const noop = () => {};
		let notify = noop;
		let seeded = false;
		let consecutiveFailures = 0;
		let unchangedPolls = 0;

		const actions: LoopActions = {
			refreshAll() {
				unchangedPolls = 0;
				manualRefresh = true;
				refreshListPending = true;
				notify();
			},
			reloadRun(runId: string) {
				unchangedPolls = 0;
				pendingRunIds.add(runId);
				notify();
			},
			wake() {
				unchangedPolls = 0;
				notify();
			},
		};

		const hasActiveRuns = () => stateRef.current.runs.some(isRunActive);

		const nextDelay = (): number | null => {
			if (seeded && !hasActiveRuns()) return null;
			if (consecutiveFailures > 0) {
				return Math.min(
					AUTO_LABEL_RUN_POLL_INTERVAL_MS * 2 ** consecutiveFailures,
					MAX_POLL_BACKOFF_MS,
				);
			}
			return Math.min(
				AUTO_LABEL_RUN_POLL_INTERVAL_MS * 2 ** unchangedPolls,
				MAX_IDLE_POLL_INTERVAL_MS,
			);
		};

		const sleep = (delayMs: number | null, onTimer: () => void) =>
			new Promise<void>((resolve) => {
				const timer =
					delayMs === null
						? null
						: setTimeout(() => {
								onTimer();
								wake();
							}, delayMs);
				function wake() {
					if (timer !== null) clearTimeout(timer);
					notify = noop;
					resolve();
				}
				notify = wake;
			});

		const fetchRunsList = async () => {
			const wasManual = manualRefresh;
			refreshListPending = false;
			manualRefresh = false;
			try {
				const resp = await readAutoLabelRunsAutoLabelRunsGet(
					{ novelId },
					{ signal: abort.signal },
				);
				if (abort.signal.aborted) return;
				if (resp.status !== 200) {
					throw new Error(`Loading autolabel runs failed: ${resp.status}`);
				}
				const prevSelectedRunId = stateRef.current.selectedRunId;
				const next = applyRunsList(stateRef.current, resp.data);
				commitState(next);
				seeded = true;
				consecutiveFailures = 0;

				if (prevSelectedRunId !== null && next.selectedRunId === null) {
					notifySelectedFromEffect({ runId: null });
				} else if (wasManual && next.selectedRunId !== null) {
					pendingRunIds.add(next.selectedRunId);
				}
			} catch (error) {
				if (abort.signal.aborted) return;
				consecutiveFailures += 1;
				console.error("Failed to load autolabel runs:", error);
			} finally {
				if (wasManual && !manualRefresh && !abort.signal.aborted) {
					setRefreshing(false);
				}
			}
		};

		const fetchRunAutoLabels = async (
			runId: string,
		): Promise<"changed" | "unchanged" | "failed"> => {
			if (!stateRef.current.runs.some((entry) => entry.run.runId === runId)) {
				return "unchanged";
			}
			try {
				const resp = await readAutoLabelsByRunAutoLabelRunsRunIdAutoLabelsGet(
					runId,
					undefined,
					{ signal: abort.signal },
				);
				if (abort.signal.aborted) return "unchanged";
				if (resp.status !== 200) {
					throw new Error(`Loading autolabels for run ${runId} failed: ${resp.status}`);
				}
				const next = applyRunAutoLabels(stateRef.current, runId, resp.data);
				const changed = commitState(next);
				if (changed && next.selectedRunId === runId) {
					notifySelectedFromEffect(toSelectedAutoLabelRun(next));
				}
				return changed ? "changed" : "unchanged";
			} catch (error) {
				if (abort.signal.aborted) return "unchanged";
				const next = applyRunError(stateRef.current, runId);
				const changed = commitState(next);
				if (changed && next.selectedRunId === runId) {
					notifySelectedFromEffect(toSelectedAutoLabelRun(next));
				}
				console.error(`Failed to load autolabels for run ${runId}:`, error);
				return "failed";
			}
		};

		const run = async () => {
			while (!abort.signal.aborted) {
				let wasTimerPoll = false;
				if (!refreshListPending && pendingRunIds.size === 0) {
					let wokenByTimer = false;
					await sleep(nextDelay(), () => {
						wokenByTimer = true;
					});
					if (abort.signal.aborted) return;
					if (!wokenByTimer) continue;
					if (!seeded) {
						refreshListPending = true;
					} else {
						wasTimerPoll = true;
						for (const entry of stateRef.current.runs) {
							if (isRunActive(entry)) pendingRunIds.add(entry.run.runId);
						}
					}
				}

				if (refreshListPending) {
					await fetchRunsList();
					if (abort.signal.aborted) return;
				}

				if (pendingRunIds.size > 0) {
					const runIds = Array.from(pendingRunIds);
					pendingRunIds.clear();
					let anyFailed = false;
					let anyChanged = false;
					for (const runId of runIds) {
						if (abort.signal.aborted) return;
						const outcome = await fetchRunAutoLabels(runId);
						if (outcome === "failed") anyFailed = true;
						else if (outcome === "changed") anyChanged = true;
					}
					if (!abort.signal.aborted) {
						if (anyFailed) {
							consecutiveFailures += 1;
							unchangedPolls = 0;
						} else if (anyChanged) {
							consecutiveFailures = 0;
							unchangedPolls = 0;
						} else if (wasTimerPoll) {
							consecutiveFailures = 0;
							unchangedPolls += 1;
						} else {
							consecutiveFailures = 0;
						}
					}
				}
			}
		};

		actionsRef.current = actions;
		void run();

		return () => {
			generationRef.current += 1;
			abort.abort();
			notify();
			actionsRef.current = null;
			stateRef.current = EMPTY_RUNS_STATE;
			setState(EMPTY_RUNS_STATE);
			setRefreshing(false);
			setCreating(false);
			notifySelectedFromEffect({ runId: null });
		};
	}, [novelId, commitState]);

	const selectRun = useCallback(
		(runId: string) => {
			const entry = stateRef.current.runs.find((candidate) => candidate.run.runId === runId);
			if (!entry) return;
			let next = applySelectRun(stateRef.current, runId);
			const shouldLoad = entry.status === "idle" || entry.status === "error";
			if (shouldLoad) {
				next = applyRunLoading(next, runId);
			}
			commitState(next);
			onSelectedRunChange?.(toSelectedAutoLabelRun(next));
			if (shouldLoad) {
				actionsRef.current?.reloadRun(runId);
			}
		},
		[commitState, onSelectedRunChange],
	);

	const deselectRun = useCallback(() => {
		const next = applySelectRun(stateRef.current, null);
		commitState(next);
		onSelectedRunChange?.({ runId: null });
	}, [commitState, onSelectedRunChange]);

	const reloadRun = useCallback(
		(runId: string) => {
			const entry = stateRef.current.runs.find((candidate) => candidate.run.runId === runId);
			if (!entry) return;
			const next = applyRunLoading(stateRef.current, runId);
			const changed = commitState(next);
			if (changed && next.selectedRunId === runId) {
				onSelectedRunChange?.(toSelectedAutoLabelRun(next));
			}
			actionsRef.current?.reloadRun(runId);
		},
		[commitState, onSelectedRunChange],
	);

	const refreshAll = useCallback(() => {
		if (novelId === null) return;
		setRefreshing(true);
		actionsRef.current?.refreshAll();
	}, [novelId]);

	const createRun = useCallback(
		async (
			params: CluenerParams | DoNothingParams,
			filter: ChapterFilter,
		): Promise<CreateAutoLabelRunResult> => {
			if (novelId === null) return { ok: false, reason: "failed" };
			const generation = generationRef.current;
			setCreating(true);
			try {
				const resp = await createAutolabelsAutoLabelsPost({
					novelId,
					params,
					start: filter.start ?? null,
					end: filter.end ?? null,
					isPublic: filter.isPublic ?? null,
					chapterIds: null,
				});
				if (generationRef.current !== generation) {
					return { ok: false, reason: "failed" };
				}
				if (resp.status === 200) {
					const next = applyRunCreated(
						stateRef.current,
						resp.data.run,
						resp.data.autolabels,
					);
					commitState(next);
					onSelectedRunChange?.(toSelectedAutoLabelRun(next));
					actionsRef.current?.wake();
					return { ok: true, run: resp.data.run };
				}
				if (resp.status === 400) return { ok: false, reason: "badRequest" };
				if (resp.status === 404) return { ok: false, reason: "notFound" };
				return { ok: false, reason: "failed" };
			} catch (error) {
				console.error("Failed to create autolabel run:", error);
				return { ok: false, reason: "failed" };
			} finally {
				if (generationRef.current === generation) {
					setCreating(false);
				}
			}
		},
		[novelId, commitState, onSelectedRunChange],
	);

	return {
		runs: state.runs,
		selectedRunId: state.selectedRunId,
		refreshing,
		creating,
		selectRun,
		deselectRun,
		reloadRun,
		refreshAll,
		createRun,
	};
}
