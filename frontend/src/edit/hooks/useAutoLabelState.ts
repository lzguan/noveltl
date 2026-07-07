import { useCallback, useMemo, useRef, useState } from "react";
import type {
	ALRProvId,
	CProvId,
	CCProvId,
	ProvAutoLabel,
	ProvAutoLabelRun,
} from "../controller/types/idTypes";

export type AutoLabelView = Omit<ProvAutoLabel, "autoLabelData"> & {
	readonly chapterId: CProvId;
};

export type AutoLabelRunView = {
	readonly run: ProvAutoLabelRun;
} & (
	| { readonly status: "idle" | "loading" | "error" }
	| {
			readonly status: "ready";
			readonly overallStatus: ProvAutoLabel["autoLabelStatus"];
			readonly autolabels: readonly AutoLabelView[];
	  }
);

export type ChapterMatchStatus = "match" | "outdated";

export function useAutoLabelState(chapterContentIds: Map<CProvId, CCProvId>) {
	const [runs, setRuns] = useState<AutoLabelRunView[]>([]);
	const [selectedRunId, setSelectedRunId] = useState<ALRProvId | null>(null);
	const [refreshing, setRefreshingState] = useState(false);
	const [promoting, setPromotingState] = useState(false);

	const runsRef = useRef<AutoLabelRunView[]>([]);
	const selectedRunIdRef = useRef<ALRProvId | null>(null);
	const refreshingRef = useRef(false);
	const promotingRef = useRef(false);

	const addRun = useCallback((run: AutoLabelRunView) => {
		runsRef.current = [...runsRef.current, run];
		setRuns([...runsRef.current]);
	}, []);

	const setRun = useCallback((runProvId: ALRProvId, run: AutoLabelRunView) => {
		const idx = runsRef.current.findIndex((r) => r.run.runId === runProvId);
		if (idx === -1) return;
		const next = [...runsRef.current];
		next[idx] = run;
		runsRef.current = next;
		setRuns([...runsRef.current]);
	}, []);

	const setRunsList = useCallback((nextRuns: AutoLabelRunView[]) => {
		runsRef.current = nextRuns;
		setRuns([...runsRef.current]);
	}, []);

	const removeRun = useCallback((runProvId: ALRProvId) => {
		runsRef.current = runsRef.current.filter((r) => r.run.runId !== runProvId);
		setRuns([...runsRef.current]);

		if (selectedRunIdRef.current === runProvId) {
			selectedRunIdRef.current = null;
			setSelectedRunId(null);
		}
	}, []);

	const setSelected = useCallback((runProvId: ALRProvId | null) => {
		selectedRunIdRef.current = runProvId;
		setSelectedRunId(runProvId);
	}, []);

	const setRefreshing = useCallback((value: boolean) => {
		refreshingRef.current = value;
		setRefreshingState(value);
	}, []);

	const setPromoting = useCallback((value: boolean) => {
		promotingRef.current = value;
		setPromotingState(value);
	}, []);

	const chapterMatchMap = useMemo(
		() =>
			new Map(
				runs.map((run) => {
					if (run.status !== "ready") {
						return [run.run.runId, new Map<CProvId, ChapterMatchStatus>()] as const;
					}
					const runMap = new Map<CProvId, ChapterMatchStatus>();
					for (const al of run.autolabels) {
						const currentCC = chapterContentIds.get(al.chapterId);
						if (currentCC === undefined) continue;
						runMap.set(
							al.chapterId,
							currentCC === al.chapterContentId ? "match" : "outdated",
						);
					}
					return [run.run.runId, runMap] as const;
				}),
			),
		[runs, chapterContentIds],
	);

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
	};
}
