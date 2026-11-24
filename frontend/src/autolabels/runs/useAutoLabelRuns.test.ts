import { act, renderHook } from "@testing-library/react";
import {
	createAutolabelsAutoLabelsPost,
	readAutoLabelRunsAutoLabelRunsGet,
	readAutoLabelsByRunAutoLabelRunsRunIdAutoLabelsGet,
} from "@/api/endpoints/default/default";
import {
	DoNothingParamsValue,
	type AutoLabelMetaWithCid,
	type AutoLabelProgress,
	type AutoLabelRun,
} from "@/api/models";
import { AUTO_LABEL_RUN_POLL_INTERVAL_MS, useAutoLabelRuns } from "./useAutoLabelRuns";

vi.mock("@/api/endpoints/default/default", () => ({
	createAutolabelsAutoLabelsPost: vi.fn(),
	readAutoLabelRunsAutoLabelRunsGet: vi.fn(),
	readAutoLabelsByRunAutoLabelRunsRunIdAutoLabelsGet: vi.fn(),
}));

const readRuns = vi.mocked(readAutoLabelRunsAutoLabelRunsGet);
const readRunAutoLabels = vi.mocked(readAutoLabelsByRunAutoLabelRunsRunIdAutoLabelsGet);
const createAutoLabels = vi.mocked(createAutolabelsAutoLabelsPost);

function makeRun(runId: string, minute = 0): AutoLabelRun {
	return {
		runId,
		novelId: "novel-1",
		triggeredBy: "user-1",
		modelName: "do_nothing",
		modelParams: DoNothingParamsValue,
		createdAt: `2026-11-22T10:${String(minute).padStart(2, "0")}:00Z`,
	};
}

function makeAutoLabel(
	autoLabelId: string,
	runId: string,
	status: AutoLabelProgress,
): AutoLabelMetaWithCid {
	return {
		chapterId: "chapter-1",
		autoLabelMeta: {
			autoLabelId,
			runId,
			chapterContentId: "cc-1",
			autoLabelStatus: status,
			autoLabelMessage: null,
			autoLabelLastJobId: null,
		},
	};
}

function runsResponse(data: AutoLabelRun[]) {
	return { status: 200 as const, data, headers: new Headers() };
}

function autoLabelsResponse(data: AutoLabelMetaWithCid[]) {
	return { status: 200 as const, data, headers: new Headers() };
}

async function advance(ms: number) {
	await act(async () => {
		await vi.advanceTimersByTimeAsync(ms);
	});
}

beforeEach(() => {
	vi.useFakeTimers();
	readRuns.mockReset();
	readRunAutoLabels.mockReset();
	createAutoLabels.mockReset();
});

afterEach(() => {
	vi.useRealTimers();
});

test("seeds runs on mount, loads selected run on demand, and polls active runs until done", async () => {
	const runA = makeRun("run-a", 1);
	readRuns.mockResolvedValueOnce(runsResponse([runA]));
	readRunAutoLabels
		.mockResolvedValueOnce(autoLabelsResponse([makeAutoLabel("al-1", "run-a", "processing")]))
		.mockResolvedValueOnce(autoLabelsResponse([makeAutoLabel("al-1", "run-a", "done")]));
	const onSelectedRunChange = vi.fn();

	const { result } = renderHook(() =>
		useAutoLabelRuns({ novelId: "novel-1", onSelectedRunChange }),
	);
	await advance(0);

	expect(readRuns).toHaveBeenCalledTimes(1);
	expect(result.current.runs.map((entry) => entry.run.runId)).toEqual(["run-a"]);
	expect(result.current.runs[0].status).toBe("idle");

	act(() => {
		result.current.selectRun("run-a");
	});
	await advance(0);

	expect(readRunAutoLabels).toHaveBeenCalledTimes(1);
	expect(result.current.selectedRunId).toBe("run-a");
	expect(result.current.runs[0].status).toBe("ready");
	expect(onSelectedRunChange).toHaveBeenLastCalledWith({
		runId: "run-a",
		status: "ready",
		autolabels: [makeAutoLabel("al-1", "run-a", "processing")],
	});

	await advance(AUTO_LABEL_RUN_POLL_INTERVAL_MS);
	expect(readRunAutoLabels).toHaveBeenCalledTimes(2);
	expect(onSelectedRunChange).toHaveBeenLastCalledWith({
		runId: "run-a",
		status: "ready",
		autolabels: [makeAutoLabel("al-1", "run-a", "done")],
	});

	// Polling stops once no runs remain active.
	await advance(AUTO_LABEL_RUN_POLL_INTERVAL_MS * 5);
	expect(readRunAutoLabels).toHaveBeenCalledTimes(2);
});

test("createRun adds and selects the new run, then polls it until finished", async () => {
	readRuns.mockResolvedValueOnce(runsResponse([]));
	const createdRun = makeRun("run-created", 5);
	const pendingAl = makeAutoLabel("al-1", "run-created", "pending");
	const doneAl = makeAutoLabel("al-1", "run-created", "done");
	createAutoLabels.mockResolvedValueOnce({
		status: 200,
		data: { run: createdRun, autolabels: [pendingAl] },
		headers: new Headers(),
	});
	readRunAutoLabels.mockResolvedValueOnce(autoLabelsResponse([doneAl]));
	const onSelectedRunChange = vi.fn();

	const { result } = renderHook(() =>
		useAutoLabelRuns({ novelId: "novel-1", onSelectedRunChange }),
	);
	await advance(0);

	await act(async () => {
		const res = await result.current.createRun(DoNothingParamsValue, { start: 1, end: 5 });
		expect(res).toEqual({ ok: true, run: createdRun });
	});

	expect(createAutoLabels).toHaveBeenCalledWith({
		novelId: "novel-1",
		params: DoNothingParamsValue,
		start: 1,
		end: 5,
		isPublic: null,
		chapterIds: null,
	});
	expect(result.current.selectedRunId).toBe("run-created");
	expect(onSelectedRunChange).toHaveBeenLastCalledWith({
		runId: "run-created",
		status: "ready",
		autolabels: [pendingAl],
	});

	await advance(AUTO_LABEL_RUN_POLL_INTERVAL_MS);
	expect(readRunAutoLabels).toHaveBeenCalledTimes(1);
	expect(onSelectedRunChange).toHaveBeenLastCalledWith({
		runId: "run-created",
		status: "ready",
		autolabels: [doneAl],
	});
});

test("createRun returns typed error reasons without mutating state", async () => {
	readRuns.mockResolvedValueOnce(runsResponse([]));
	createAutoLabels.mockResolvedValueOnce({
		status: 400,
		data: { detail: "Invalid range" },
		headers: new Headers(),
	});

	const { result } = renderHook(() => useAutoLabelRuns({ novelId: "novel-1" }));
	await advance(0);

	await act(async () => {
		expect(await result.current.createRun(DoNothingParamsValue, {})).toEqual({
			ok: false,
			reason: "badRequest",
		});
	});
	expect(result.current.runs).toEqual([]);
	expect(result.current.creating).toBe(false);
});

test("a poll that changes nothing does not trigger extra re-renders", async () => {
	const runA = makeRun("run-a", 1);
	readRuns.mockResolvedValueOnce(runsResponse([runA]));
	readRunAutoLabels.mockResolvedValue(
		autoLabelsResponse([makeAutoLabel("al-1", "run-a", "processing")]),
	);
	let renders = 0;

	const { result } = renderHook(() => {
		renders += 1;
		return useAutoLabelRuns({ novelId: "novel-1" });
	});
	await advance(0);
	act(() => {
		result.current.selectRun("run-a");
	});
	await advance(0);
	const rendersAfterFirstLoad = renders;

	await advance(AUTO_LABEL_RUN_POLL_INTERVAL_MS * 3);
	expect(readRunAutoLabels.mock.calls.length).toBeGreaterThanOrEqual(3);
	expect(renders).toBe(rendersAfterFirstLoad);
});

test("refreshAll reloads the run list and re-fetches the selected run", async () => {
	const runA = makeRun("run-a", 1);
	const runB = makeRun("run-b", 2);
	readRuns
		.mockResolvedValueOnce(runsResponse([runA]))
		.mockResolvedValueOnce(runsResponse([runA, runB]));
	readRunAutoLabels
		.mockResolvedValueOnce(autoLabelsResponse([makeAutoLabel("al-1", "run-a", "done")]))
		.mockResolvedValueOnce(autoLabelsResponse([makeAutoLabel("al-1", "run-a", "done")]));

	const { result } = renderHook(() => useAutoLabelRuns({ novelId: "novel-1" }));
	await advance(0);

	act(() => {
		result.current.selectRun("run-a");
	});
	await advance(0);
	expect(readRunAutoLabels).toHaveBeenCalledTimes(1);

	act(() => {
		result.current.refreshAll();
	});
	await advance(0);

	expect(readRuns).toHaveBeenCalledTimes(2);
	expect(readRunAutoLabels).toHaveBeenCalledTimes(2);
	expect(result.current.refreshing).toBe(false);
	expect(result.current.runs.map((entry) => entry.run.runId)).toEqual(["run-b", "run-a"]);
});
