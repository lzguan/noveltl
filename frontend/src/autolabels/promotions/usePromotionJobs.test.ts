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
