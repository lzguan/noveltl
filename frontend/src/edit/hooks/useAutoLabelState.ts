import { useCallback, useState } from "react";
import type {
	ALRProvId,
	ALRServId,
	CProvId,
	ProvAutoLabel,
	ProvAutoLabelRun,
} from "../controller/types/idTypes";
import { useSyncState } from "../utils/useSyncState";

export type AutoLabelView = Omit<ProvAutoLabel, "autoLabelData"> & {
	readonly chapterId: CProvId;
};

export type AutoLabelRunView = {
	readonly run: ProvAutoLabelRun & { readonly servId: ALRServId | null };
} & (
	| { readonly status: "idle" | "loading" | "error" }
	| {
			readonly status: "ready";
			readonly overallStatus: ProvAutoLabel["autoLabelStatus"];
			readonly autolabels: readonly AutoLabelView[];
	  }
);

export type ChapterMatchStatus = "match" | "outdated";

export function useAutoLabelState() {
	const [runs, runsRef, commitRuns] = useSyncState<AutoLabelRunView[]>([]);
	const [selectedRunId, selectedRunIdRef, commitSelectedRunId] = useSyncState<ALRProvId | null>(
		null,
	);
	const [refreshing, refreshingRef, commitRefreshing] = useSyncState(false);
	const [promoting, promotingRef, commitPromoting] = useSyncState(false);

	const addRun = useCallback(
		(run: AutoLabelRunView) => {
			runsRef.current = [...runsRef.current, run];
			commitRuns();
		},
		[runsRef, commitRuns],
	);

	const setRun = useCallback(
		(runProvId: ALRProvId, run: AutoLabelRunView) => {
			const idx = runsRef.current.findIndex((r) => r.run.runId === runProvId);
			if (idx === -1) return;
			const next = [...runsRef.current];
			next[idx] = run;
			runsRef.current = next;
			commitRuns();
		},
		[runsRef, commitRuns],
	);

	const setRunsList = useCallback(
		(nextRuns: AutoLabelRunView[]) => {
			runsRef.current = nextRuns;
			commitRuns();
		},
		[runsRef, commitRuns],
	);

	const removeRun = useCallback(
		(runProvId: ALRProvId) => {
			runsRef.current = runsRef.current.filter((r) => r.run.runId !== runProvId);
			commitRuns();

			if (selectedRunIdRef.current === runProvId) {
				selectedRunIdRef.current = null;
				commitSelectedRunId();
			}
		},
		[runsRef, commitRuns, commitSelectedRunId, selectedRunIdRef],
	);

	const setSelected = useCallback(
		(runProvId: ALRProvId | null) => {
			selectedRunIdRef.current = runProvId;
			commitSelectedRunId();
		},
		[selectedRunIdRef, commitSelectedRunId],
	);

	const setRefreshing = useCallback(
		(value: boolean) => {
			refreshingRef.current = value;
			commitRefreshing();
		},
		[refreshingRef, commitRefreshing],
	);

	const setPromoting = useCallback(
		(value: boolean) => {
			promotingRef.current = value;
			commitPromoting();
		},
		[promotingRef, commitPromoting],
	);

	const [chapterMatchMap, setChapterMatchMap] = useState<
		Map<ALRProvId, Map<CProvId, ChapterMatchStatus>>
	>(new Map());

	return {
		runs,
		selectedRunId,
		refreshing,
		promoting,
		chapterMatchMap,
		runsRef,
		selectedRunIdRef,
		refreshingRef,
		promotingRef,
		addRun,
		setRun,
		setRunsList,
		removeRun,
		setSelected,
		setRefreshing,
		setPromoting,
		setChapterMatchMap,
	};
}
