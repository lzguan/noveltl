import {
	DoNothingParamsValue,
	type AutoLabelMetaWithCid,
	type AutoLabelProgress,
	type AutoLabelRun,
} from "@/api/models";
import {
	applyRunAutoLabels,
	applyRunCreated,
	applyRunError,
	applyRunLoading,
	applyRunsList,
	applySelectRun,
	deriveOverallStatus,
	EMPTY_RUNS_STATE,
	getChapterMatchStatus,
	isRunActive,
	sameRunsState,
} from "./autoLabelRunsState";

function makeRun(runId: string, createdAt: string): AutoLabelRun {
	return {
		runId,
		novelId: "novel-1",
		triggeredBy: "user-1",
		modelName: "do_nothing",
		modelParams: DoNothingParamsValue,
		createdAt,
	};
}

function makeAutoLabel(
	autoLabelId: string,
	runId: string,
	chapterId: string,
	chapterContentId: string,
	status: AutoLabelProgress,
): AutoLabelMetaWithCid {
	return {
		chapterId,
		autoLabelMeta: {
			autoLabelId,
			runId,
			chapterContentId,
			autoLabelStatus: status,
			autoLabelMessage: null,
			autoLabelLastJobId: null,
		},
	};
}

test("applyRunsList sorts newest first, preserves loaded runs, and clears vanished selection", () => {
	const runA = makeRun("run-a", "2026-11-22T10:00:00Z");
	const runB = makeRun("run-b", "2026-11-22T11:00:00Z");
	const runC = makeRun("run-c", "2026-11-22T12:00:00Z");

	let state = applyRunsList(EMPTY_RUNS_STATE, [runA, runB]);
	expect(state.runs.map((entry) => entry.run.runId)).toEqual(["run-b", "run-a"]);

	const alA = makeAutoLabel("al-1", "run-a", "ch-1", "cc-1", "done");
	state = applyRunAutoLabels(state, "run-a", [alA]);
	state = applySelectRun(state, "run-b");

	const refreshed = applyRunsList(state, [runA, runC]);
	expect(refreshed.runs.map((entry) => entry.run.runId)).toEqual(["run-c", "run-a"]);
	expect(refreshed.selectedRunId).toBeNull();
	expect(refreshed.runs[0].status).toBe("idle");
	expect(refreshed.runs[1].status).toBe("ready");
	if (refreshed.runs[1].status === "ready") {
		expect(refreshed.runs[1].autolabels).toEqual([alA]);
	}
});

test("applyRunCreated inserts and selects a ready run with derived status", () => {
	const runOld = makeRun("run-old", "2026-11-22T10:00:00Z");
	const runNew = makeRun("run-new", "2026-11-22T11:00:00Z");
	const initial = applyRunsList(EMPTY_RUNS_STATE, [runOld]);

	const next = applyRunCreated(initial, runNew, [
		makeAutoLabel("al-1", "run-new", "ch-1", "cc-1", "pending"),
		makeAutoLabel("al-2", "run-new", "ch-2", "cc-2", "processing"),
	]);

	expect(next.selectedRunId).toBe("run-new");
	expect(next.runs.map((entry) => entry.run.runId)).toEqual(["run-new", "run-old"]);
	expect(next.runs[0].status).toBe("ready");
	expect(isRunActive(next.runs[0])).toBe(true);
	if (next.runs[0].status === "ready") {
		expect(next.runs[0].overallStatus).toBe("processing");
	}
});

test("applyRunLoading and applyRunError keep existing ready data intact", () => {
	const runA = makeRun("run-a", "2026-11-22T10:00:00Z");
	let state = applyRunsList(EMPTY_RUNS_STATE, [runA]);
	state = applyRunLoading(state, "run-a");
	expect(state.runs[0].status).toBe("loading");

	state = applyRunError(state, "run-a");
	expect(state.runs[0].status).toBe("error");

	state = applyRunAutoLabels(state, "run-a", [
		makeAutoLabel("al-1", "run-a", "ch-1", "cc-1", "done"),
	]);
	expect(applyRunLoading(state, "run-a")).toBe(state);
	expect(applyRunError(state, "run-a")).toBe(state);
});

test("deriveOverallStatus prioritizes processing, pending, all-failed, then done", () => {
	expect(deriveOverallStatus([])).toBe("done");
	expect(
		deriveOverallStatus([
			makeAutoLabel("1", "r", "c1", "cc1", "failed"),
			makeAutoLabel("2", "r", "c2", "cc2", "failed"),
		]),
	).toBe("failed");
	expect(
		deriveOverallStatus([
			makeAutoLabel("1", "r", "c1", "cc1", "failed"),
			makeAutoLabel("2", "r", "c2", "cc2", "done"),
		]),
	).toBe("done");
	expect(
		deriveOverallStatus([
			makeAutoLabel("1", "r", "c1", "cc1", "pending"),
			makeAutoLabel("2", "r", "c2", "cc2", "done"),
		]),
	).toBe("pending");
});

test("getChapterMatchStatus reports match, outdated, or undefined when closed", () => {
	const open = new Map<string, string | null>([
		["ch-1", "cc-1"],
		["ch-2", null],
	]);
	expect(getChapterMatchStatus("ch-1", "cc-1", open)).toBe("match");
	expect(getChapterMatchStatus("ch-1", "cc-old", open)).toBe("outdated");
	expect(getChapterMatchStatus("ch-2", "cc-2", open)).toBe("outdated");
	expect(getChapterMatchStatus("ch-3", "cc-3", open)).toBeUndefined();
});

test("sameRunsState treats structurally identical states as equal", () => {
	const runA = makeRun("run-a", "2026-11-22T10:00:00Z");
	const al = makeAutoLabel("al-1", "run-a", "ch-1", "cc-1", "processing");
	const a = applyRunAutoLabels(applyRunsList(EMPTY_RUNS_STATE, [runA]), "run-a", [al]);
	const b = applyRunAutoLabels(a, "run-a", [{ ...al, autoLabelMeta: { ...al.autoLabelMeta } }]);
	expect(sameRunsState(a, b)).toBe(true);
});
