import { useCallback, useEffect, useMemo, useState } from "react";
import { readAutolabelByIdAutoLabelsAutoLabelIdGet } from "@/api/endpoints/default/default";
import type { LabelBase } from "@/api/models";
import type { SelectedAutoLabelRun } from "@/autolabels/runs/autoLabelRunsState";
import { labelsToUtf16 } from "../utils/textPositions";

export type AutoLabelPreview = readonly LabelBase[];

export type AutoLabelPreviewTarget = {
	readonly chapterId: string;
	readonly chapterContentId: string;
	readonly text: string;
};

export function useAutoLabelPreview(
	selectedRun: SelectedAutoLabelRun,
	target: AutoLabelPreviewTarget | null,
) {
	const [enabled, setEnabledState] = useState(false);
	const [attempt, setAttempt] = useState(0);
	const [cache, setCache] = useState<ReadonlyMap<string, readonly LabelBase[]>>(() => new Map());
	const [failedKey, setFailedKey] = useState<string | null>(null);

	const setEnabled = useCallback((next: boolean) => {
		setEnabledState(next);
		if (next) setAttempt((count) => count + 1);
	}, []);

	const matchingAutoLabelId = useMemo(() => {
		if (
			!enabled ||
			target === null ||
			selectedRun.runId === null ||
			selectedRun.status !== "ready"
		) {
			return null;
		}
		const matching = selectedRun.autolabels.find(
			(al) =>
				al.chapterId === target.chapterId &&
				al.autoLabelMeta.chapterContentId === target.chapterContentId &&
				al.autoLabelMeta.autoLabelStatus === "done",
		);
		return matching?.autoLabelMeta.autoLabelId ?? null;
	}, [enabled, target, selectedRun]);

	const cachedLabels = matchingAutoLabelId !== null ? cache.get(matchingAutoLabelId) : undefined;
	const fetchKey = matchingAutoLabelId !== null ? `${matchingAutoLabelId}:${attempt}` : null;
	const needsFetch = fetchKey !== null && cachedLabels === undefined && failedKey !== fetchKey;

	useEffect(() => {
		if (!needsFetch || matchingAutoLabelId === null || fetchKey === null) return;
		const abort = new AbortController();
		const autoLabelId = matchingAutoLabelId;
		const key = fetchKey;

		void readAutolabelByIdAutoLabelsAutoLabelIdGet(autoLabelId, { signal: abort.signal })
			.then((resp) => {
				if (abort.signal.aborted) return;
				if (resp.status !== 200) {
					setFailedKey(key);
					return;
				}
				const labels = resp.data.autoLabelData ? [...resp.data.autoLabelData] : [];
				setCache((prev) => {
					const next = new Map(prev);
					next.set(autoLabelId, labels);
					return next;
				});
			})
			.catch((err: unknown) => {
				if (abort.signal.aborted) return;
				setFailedKey(key);
				console.error("Failed to load autolabel preview data:", err);
			});

		return () => {
			abort.abort();
		};
	}, [needsFetch, matchingAutoLabelId, fetchKey]);

	const preview = useMemo<AutoLabelPreview | null>(() => {
		if (target === null || cachedLabels === undefined) return null;
		return labelsToUtf16(target.text, cachedLabels);
	}, [target, cachedLabels]);

	const loading =
		(enabled &&
			target !== null &&
			selectedRun.runId !== null &&
			selectedRun.status === "loading") ||
		needsFetch;

	return {
		enabled,
		loading,
		preview,
		setEnabled,
	};
}
