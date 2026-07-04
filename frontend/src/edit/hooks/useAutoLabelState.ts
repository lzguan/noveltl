import { useCallback, useRef, useState } from "react";
import type {
	ALRProvId,
	CProvId,
	ProvAutoLabel,
	ProvAutoLabelRun,
} from "../controller/types/idTypes";

export type AutoLabelView = Omit<ProvAutoLabel, "autoLabelData"> & {
	readonly chapterId: CProvId;
};

export type AutoLabelRunView = {
	readonly run: ProvAutoLabelRun;
	readonly overallStatus: ProvAutoLabel["autoLabelStatus"];
	readonly autolabels: readonly AutoLabelView[];
};

export type PromotionChapterFilter = {
	readonly start?: number;
	readonly end?: number;
};

export function useAutoLabelState() {
	const [runs, setRuns] = useState<AutoLabelRunView[]>([]);
	const [selectedRunId, setSelectedRunId] = useState<ALRProvId | null>(null);
	const [promotionChapterFilter, setPromotionChapterFilter] = useState<PromotionChapterFilter>(
		{},
	);

	const runsRef = useRef<AutoLabelRunView[]>([]);
	const selectedRunIdRef = useRef<ALRProvId | null>(null);
	const promotionChapterFilterRef = useRef<PromotionChapterFilter>({});

	const addRun = useCallback((run: AutoLabelRunView) => {
		runsRef.current = [...runsRef.current, run];
		setRuns([...runsRef.current]);
	}, []);

	const setRun = useCallback((runProvId: ALRProvId, run: AutoLabelRunView) => {
		const idx = runsRef.current.findIndex((r) => r.run.runId === runProvId);
		if (idx === -1) {
			return;
		} else {
			const next = [...runsRef.current];
			next[idx] = run;
			runsRef.current = next;
		}
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

	const setPromoFilter = useCallback((filter: PromotionChapterFilter) => {
		promotionChapterFilterRef.current = filter;
		setPromotionChapterFilter(filter);
	}, []);

	return {
		runs,
		selectedRunId,
		promotionChapterFilter,
		runsRef,
		selectedRunIdRef,
		promotionChapterFilterRef,
		addRun,
		setRun,
		removeRun,
		setSelected,
		setPromoFilter,
	};
}
