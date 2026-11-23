import { act, renderHook } from "@testing-library/react";
import {
	createLabelPromotionLabelGroupsLabelGroupIdLabelPromotionsPost,
	readLabelPromotionsNovelsNovelIdLabelPromotionsGet,
} from "@/api/endpoints/default/default";
import type { LabelPromotionJob } from "@/api/models";
import { MAX_TRACKED_PROMOTIONS } from "./promotionJobsState";
import { PROMOTION_POLL_INTERVAL_MS, usePromotionJobs } from "./usePromotionJobs";

vi.mock("@/api/endpoints/default/default", () => ({
	createLabelPromotionLabelGroupsLabelGroupIdLabelPromotionsPost: vi.fn(),
	readLabelPromotionsNovelsNovelIdLabelPromotionsGet: vi.fn(),
}));

const read = vi.mocked(readLabelPromotionsNovelsNovelIdLabelPromotionsGet);
const create = vi.mocked(createLabelPromotionLabelGroupsLabelGroupIdLabelPromotionsPost);

function job(
	promotionId: string,
	status: LabelPromotionJob["status"],
	minute = 0,
): LabelPromotionJob {
	const at = `2026-11-22T10:${String(minute).padStart(2, "0")}:00Z`;
	return {
		promotionId,
		runId: "run",
		labelGroupId: "group",
		skipExistingLabels: true,
		status,
		message: null,
		counts: { total: 1, done: 0, failed: 0, pending: 1 },
		createdAt: at,
		updatedAt: at,
	};
}

function listResponse(data: LabelPromotionJob[]) {
	return { status: 200 as const, data, headers: new Headers() };
}

function requestedIds(callIndex: number): string[] | null | undefined {
	return read.mock.calls[callIndex][1]?.promotionIds;
}

async function advance(ms: number) {
	await act(async () => {
		await vi.advanceTimersByTimeAsync(ms);
	});
}

beforeEach(() => {
	vi.useFakeTimers();
	read.mockReset();
	create.mockReset();
});

afterEach(() => {
	vi.useRealTimers();
});

test("polls active jobs until they finish and reports each finish once", async () => {
	read.mockResolvedValueOnce(
		listResponse([job("a", "processing"), job("old", "done")]),
	).mockResolvedValueOnce(listResponse([job("a", "done", 1)]));
	const onJobFinished = vi.fn();

	const { result } = renderHook(() => usePromotionJobs({ novelId: "novel", onJobFinished }));
	await advance(0);
	expect(result.current.jobs.map((j) => j.promotionId)).toEqual(["a", "old"]);

	await advance(PROMOTION_POLL_INTERVAL_MS);
	expect(requestedIds(1)).toEqual(["a"]);
	expect(onJobFinished).toHaveBeenCalledExactlyOnceWith(job("a", "done", 1));
	expect(result.current.activeCount).toBe(0);
	expect(result.current.jobs.map((j) => j.promotionId)).toEqual(["a", "old"]);

	await advance(PROMOTION_POLL_INTERVAL_MS * 5);
	expect(read).toHaveBeenCalledTimes(2);
});

test("a job queued while a poll is in flight is kept and polled next", async () => {
	let resolvePoll: (value: ReturnType<typeof listResponse>) => void = () => {};
	read.mockResolvedValueOnce(listResponse([job("a", "processing")]))
		.mockReturnValueOnce(
			new Promise((resolve) => {
				resolvePoll = resolve;
			}),
		)
		.mockResolvedValueOnce(listResponse([job("a", "processing"), job("b", "pending", 1)]));
	create.mockResolvedValue({
		status: 202,
		data: { promotionId: "b", itemCount: 1 },
		headers: new Headers(),
	});

	const { result } = renderHook(() =>
		usePromotionJobs({ novelId: "novel", onJobFinished: vi.fn() }),
	);
	await advance(PROMOTION_POLL_INTERVAL_MS);
	expect(requestedIds(1)).toEqual(["a"]);

	await act(async () => {
		expect(await result.current.queue("group", { runId: "run" })).toEqual({
			ok: true,
			promotionId: "b",
			itemCount: 1,
		});
	});
	await act(async () => {
		resolvePoll(listResponse([job("a", "processing")]));
	});
	await advance(0);

	expect(requestedIds(2)).toEqual(["a", "b"]);
	expect(result.current.jobs.map((j) => j.promotionId)).toEqual(["b", "a"]);
});

test("refuses to queue past the cap and reseeds on a conflict", async () => {
	const active = Array.from({ length: MAX_TRACKED_PROMOTIONS }, (_, i) =>
		job(`job-${i}`, "processing", i),
	);
	read.mockResolvedValue(listResponse(active));
	create.mockResolvedValue({
		status: 409,
		data: { detail: "A promotion for this run and group is running." },
		headers: new Headers(),
	});

	const { result } = renderHook(() =>
		usePromotionJobs({ novelId: "novel", onJobFinished: vi.fn() }),
	);
	await advance(0);

	await act(async () => {
		expect(await result.current.queue("group", { runId: "run" })).toEqual({
			ok: false,
			reason: "tooMany",
		});
	});
	expect(create).not.toHaveBeenCalled();

	read.mockResolvedValue(listResponse([]));
	await advance(PROMOTION_POLL_INTERVAL_MS);
	const callsBefore = read.mock.calls.length;
	await act(async () => {
		expect(await result.current.queue("group", { runId: "run" })).toEqual({
			ok: false,
			reason: "alreadyActive",
		});
	});
	expect(read.mock.calls[callsBefore][1]).toEqual({ limit: MAX_TRACKED_PROMOTIONS });
});

test("a poll that changes nothing does not re-render", async () => {
	read.mockResolvedValue(listResponse([job("a", "processing")]));
	let renders = 0;

	renderHook(() => {
		renders += 1;
		return usePromotionJobs({ novelId: "novel", onJobFinished: vi.fn() });
	});
	await advance(0);
	const rendersAfterSeed = renders;

	await advance(PROMOTION_POLL_INTERVAL_MS * 3);
	expect(read.mock.calls.length).toBeGreaterThanOrEqual(3);
	expect(renders).toBe(rendersAfterSeed);
});

test("a job queued during a reseed that lists it as finished reports its finish once without repolling", async () => {
	let resolveReseed: (value: ReturnType<typeof listResponse>) => void = () => {};
	read.mockResolvedValueOnce(listResponse([])).mockReturnValueOnce(
		new Promise((resolve) => {
			resolveReseed = resolve;
		}),
	);
	create.mockResolvedValue({
		status: 202,
		data: { promotionId: "a", itemCount: 1 },
		headers: new Headers(),
	});
	const onJobFinished = vi.fn();

	const { result } = renderHook(() => usePromotionJobs({ novelId: "novel", onJobFinished }));
	await advance(0);
	act(() => result.current.refresh());
	await advance(0);
	await act(async () => {
		await result.current.queue("group", { runId: "run" });
	});
	await act(async () => {
		resolveReseed(listResponse([job("a", "done", 1)]));
	});
	await advance(PROMOTION_POLL_INTERVAL_MS * 2);

	expect(read).toHaveBeenCalledTimes(2);
	expect(read.mock.calls[1][1]).toEqual({ limit: MAX_TRACKED_PROMOTIONS });
	expect(onJobFinished).toHaveBeenCalledExactlyOnceWith(job("a", "done", 1));
	expect(result.current.jobs.map((j) => j.promotionId)).toEqual(["a"]);
});

test("a queued job that becomes active then finishes across two reseeds only reports its finish once", async () => {
	let resolveFirstReseed: (value: ReturnType<typeof listResponse>) => void = () => {};
	read.mockResolvedValueOnce(listResponse([]))
		.mockReturnValueOnce(
			new Promise((resolve) => {
				resolveFirstReseed = resolve;
			}),
		)
		.mockResolvedValueOnce(listResponse([job("a", "done", 1)]));
	create.mockResolvedValue({
		status: 202,
		data: { promotionId: "a", itemCount: 1 },
		headers: new Headers(),
	});
	const onJobFinished = vi.fn();

	const { result } = renderHook(() => usePromotionJobs({ novelId: "novel", onJobFinished }));
	await advance(0);
	act(() => result.current.refresh());
	await advance(0);
	await act(async () => {
		await result.current.queue("group", { runId: "run" });
	});
	act(() => result.current.refresh());
	await act(async () => {
		resolveFirstReseed(listResponse([job("a", "processing", 0)]));
	});
	await advance(PROMOTION_POLL_INTERVAL_MS * 2);

	expect(read).toHaveBeenCalledTimes(3);
	expect(read.mock.calls[2][1]).toEqual({ limit: MAX_TRACKED_PROMOTIONS });
	expect(onJobFinished).toHaveBeenCalledExactlyOnceWith(job("a", "done", 1));
	expect(result.current.jobs.map((j) => j.promotionId)).toEqual(["a"]);
});

test("counts a queued job listed by a reseed once when admitting another job", async () => {
	const active = Array.from({ length: MAX_TRACKED_PROMOTIONS - 2 }, (_, i) =>
		job(String(i), "processing"),
	);
	let resolveSeed: (value: ReturnType<typeof listResponse>) => void = () => {};
	read.mockReturnValueOnce(
		new Promise((resolve) => {
			resolveSeed = resolve;
		}),
	).mockReturnValueOnce(new Promise(() => {}));
	create.mockImplementation(async (_group, { runId }) => ({
		status: 202,
		data: { promotionId: runId, itemCount: 1 },
		headers: new Headers(),
	}));
	const { result } = renderHook(() =>
		usePromotionJobs({ novelId: "novel", onJobFinished: vi.fn() }),
	);
	await act(async () => {
		await result.current.queue("group", { runId: "overlap" });
	});
	await act(async () => {
		resolveSeed(listResponse([...active, job("overlap", "pending")]));
	});
	await act(async () => {
		expect(await result.current.queue("group", { runId: "tenth" })).toMatchObject({ ok: true });
		expect(await result.current.queue("group", { runId: "eleventh" })).toEqual({
			ok: false,
			reason: "tooMany",
		});
	});
});
