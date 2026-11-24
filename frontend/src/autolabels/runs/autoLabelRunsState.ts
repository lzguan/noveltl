import type { AutoLabelMetaWithCid, AutoLabelProgress, AutoLabelRun } from "@/api/models";

export type ChapterFilter = {
	readonly start?: number;
	readonly end?: number;
	readonly isPublic?: boolean;
};

export type ChapterMatchStatus = "match" | "outdated";

export type AutoLabelRunEntry = {
	readonly run: AutoLabelRun;
} & (
	| { readonly status: "idle" | "loading" | "error" }
	| {
			readonly status: "ready";
			readonly overallStatus: AutoLabelProgress;
			readonly autolabels: readonly AutoLabelMetaWithCid[];
	  }
);

export type SelectedAutoLabelRun =
	| { readonly runId: null }
	| { readonly runId: string; readonly status: "idle" | "loading" | "error" }
	| {
			readonly runId: string;
			readonly status: "ready";
			readonly autolabels: readonly AutoLabelMetaWithCid[];
	  };

export type AutoLabelRunsState = {
	readonly runs: readonly AutoLabelRunEntry[];
	readonly selectedRunId: string | null;
};

export const EMPTY_RUNS_STATE: AutoLabelRunsState = {
	runs: [],
	selectedRunId: null,
};

export function formatRunLabel(run: AutoLabelRun): string {
	return `Run ${run.runId.slice(0, 8)}`;
}

export function deriveOverallStatus(
	autolabels: readonly AutoLabelMetaWithCid[],
): AutoLabelProgress {
	if (autolabels.some((al) => al.autoLabelMeta.autoLabelStatus === "processing")) {
		return "processing";
	}
	if (autolabels.some((al) => al.autoLabelMeta.autoLabelStatus === "pending")) {
		return "pending";
	}
	if (
		autolabels.length > 0 &&
		autolabels.every((al) => al.autoLabelMeta.autoLabelStatus === "failed")
	) {
		return "failed";
	}
	return "done";
}

export function isRunActive(entry: AutoLabelRunEntry): boolean {
	return (
		entry.status === "ready" &&
		(entry.overallStatus === "pending" || entry.overallStatus === "processing")
	);
}

export function getChapterMatchStatus(
	chapterId: string,
	chapterContentId: string,
	openChapterContentIds: ReadonlyMap<string, string | null>,
): ChapterMatchStatus | undefined {
	if (!openChapterContentIds.has(chapterId)) return undefined;
	const currentContentId = openChapterContentIds.get(chapterId);
	return currentContentId !== null && currentContentId === chapterContentId
		? "match"
		: "outdated";
}

export function toSelectedAutoLabelRun(state: AutoLabelRunsState): SelectedAutoLabelRun {
	if (state.selectedRunId === null) return { runId: null };
	const entry = state.runs.find((candidate) => candidate.run.runId === state.selectedRunId);
	if (!entry) return { runId: null };
	if (entry.status === "ready") {
		return { runId: entry.run.runId, status: "ready", autolabels: entry.autolabels };
	}
	return { runId: entry.run.runId, status: entry.status };
}

function createdAtMs(run: AutoLabelRun): number {
	const time = Date.parse(run.createdAt);
	return Number.isNaN(time) ? 0 : time;
}

function sortEntries(entries: readonly AutoLabelRunEntry[]): AutoLabelRunEntry[] {
	return [...entries].sort((a, b) => createdAtMs(b.run) - createdAtMs(a.run));
}

export function applyRunsList(
	previous: AutoLabelRunsState,
	runs: readonly AutoLabelRun[],
): AutoLabelRunsState {
	const existing = new Map(previous.runs.map((entry) => [entry.run.runId, entry]));
	const nextRuns = sortEntries(
		runs.map((run) => {
			const prev = existing.get(run.runId);
			if (!prev) return { run, status: "idle" as const };
			if (prev.status === "ready") {
				return {
					run,
					status: "ready" as const,
					overallStatus: prev.overallStatus,
					autolabels: prev.autolabels,
				};
			}
			return { run, status: prev.status };
		}),
	);
	const selectedStillPresent =
		previous.selectedRunId !== null &&
		nextRuns.some((entry) => entry.run.runId === previous.selectedRunId);
	return {
		runs: nextRuns,
		selectedRunId: selectedStillPresent ? previous.selectedRunId : null,
	};
}

export function applyRunCreated(
	previous: AutoLabelRunsState,
	run: AutoLabelRun,
	autolabels: readonly AutoLabelMetaWithCid[],
): AutoLabelRunsState {
	const nextEntry: AutoLabelRunEntry = {
		run,
		status: "ready",
		overallStatus: deriveOverallStatus(autolabels),
		autolabels: [...autolabels],
	};
	const remaining = previous.runs.filter((entry) => entry.run.runId !== run.runId);
	return {
		runs: sortEntries([nextEntry, ...remaining]),
		selectedRunId: run.runId,
	};
}

export function applyRunLoading(
	previous: AutoLabelRunsState,
	runId: string,
): AutoLabelRunsState {
	const idx = previous.runs.findIndex((entry) => entry.run.runId === runId);
	if (idx === -1) return previous;
	const current = previous.runs[idx];
	if (current.status === "ready" || current.status === "loading") return previous;
	const nextRuns = [...previous.runs];
	nextRuns[idx] = { run: current.run, status: "loading" };
	return { ...previous, runs: nextRuns };
}

export function applyRunAutoLabels(
	previous: AutoLabelRunsState,
	runId: string,
	autolabels: readonly AutoLabelMetaWithCid[],
): AutoLabelRunsState {
	const idx = previous.runs.findIndex((entry) => entry.run.runId === runId);
	if (idx === -1) return previous;
	const current = previous.runs[idx];
	const nextRuns = [...previous.runs];
	nextRuns[idx] = {
		run: current.run,
		status: "ready",
		overallStatus: deriveOverallStatus(autolabels),
		autolabels: [...autolabels],
	};
	return { ...previous, runs: nextRuns };
}

export function applyRunError(previous: AutoLabelRunsState, runId: string): AutoLabelRunsState {
	const idx = previous.runs.findIndex((entry) => entry.run.runId === runId);
	if (idx === -1) return previous;
	const current = previous.runs[idx];
	if (current.status === "ready" || current.status === "error") return previous;
	const nextRuns = [...previous.runs];
	nextRuns[idx] = { run: current.run, status: "error" };
	return { ...previous, runs: nextRuns };
}

export function applySelectRun(
	previous: AutoLabelRunsState,
	runId: string | null,
): AutoLabelRunsState {
	if (runId === null) {
		return previous.selectedRunId === null ? previous : { ...previous, selectedRunId: null };
	}
	if (!previous.runs.some((entry) => entry.run.runId === runId)) return previous;
	if (previous.selectedRunId === runId) return previous;
	return { ...previous, selectedRunId: runId };
}

function sameAutoLabels(
	a: readonly AutoLabelMetaWithCid[],
	b: readonly AutoLabelMetaWithCid[],
): boolean {
	return (
		a.length === b.length &&
		a.every((item, index) => {
			const other = b[index];
			return (
				item.chapterId === other.chapterId &&
				item.autoLabelMeta.autoLabelId === other.autoLabelMeta.autoLabelId &&
				item.autoLabelMeta.chapterContentId === other.autoLabelMeta.chapterContentId &&
				item.autoLabelMeta.autoLabelStatus === other.autoLabelMeta.autoLabelStatus &&
				item.autoLabelMeta.autoLabelMessage === other.autoLabelMeta.autoLabelMessage &&
				item.autoLabelMeta.autoLabelLastJobId === other.autoLabelMeta.autoLabelLastJobId
			);
		})
	);
}

function sameRunEntry(a: AutoLabelRunEntry, b: AutoLabelRunEntry): boolean {
	if (a.run.runId !== b.run.runId || a.run.createdAt !== b.run.createdAt) return false;
	if (a.status !== b.status) return false;
	if (a.status !== "ready" || b.status !== "ready") return true;
	return a.overallStatus === b.overallStatus && sameAutoLabels(a.autolabels, b.autolabels);
}

export function sameRunsState(a: AutoLabelRunsState, b: AutoLabelRunsState): boolean {
	return (
		a.selectedRunId === b.selectedRunId &&
		a.runs.length === b.runs.length &&
		a.runs.every((entry, index) => sameRunEntry(entry, b.runs[index]))
	);
}
