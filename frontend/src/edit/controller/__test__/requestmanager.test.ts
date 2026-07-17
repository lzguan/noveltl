import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Effect } from "effect";
import { buildRequestManager } from "../requestmanager";
import { buildIdRepository } from "../idRepository";
import { IdempotentCallable } from "../types/helperTypes";
import { CacheConflictException, FatalException } from "../types/errors";
import type { TriggerEvent } from "../types/controllerTypes";
import type { RequestEvent, RequestKey, ReserveList } from "../types/requestTypes";
import { CCServId } from "../types/idTypes";
import { getCachedResultCachedCachedIdGet } from "@/api/endpoints/default/default";

vi.mock("@/api/endpoints/default/default", async (importOriginal) => {
	const actual = await importOriginal<typeof import("@/api/endpoints/default/default")>();
	return {
		...actual,
		getCachedResultCachedCachedIdGet: vi.fn(),
	};
});

const emptyReserveList: ReserveList = {
	autoLabel: [],
	autoLabelRun: [],
	chapter: [],
	chapterContent: [],
	label: [],
	labelData: [],
	labelGroup: [],
};

describe("buildRequestManager", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it("retries cached requests with a new key after a cache conflict", async () => {
		const getCachedResultMock = vi.mocked(getCachedResultCachedCachedIdGet);
		const sentKeys: RequestKey[] = [];
		const postSendResults: unknown[] = [];
		const errors: TriggerEvent[] = [];
		let sendAttempts = 0;
		const requestManager = Effect.runSync(
			buildRequestManager(buildIdRepository(), (event) =>
				Effect.sync(() => {
					errors.push(event);
				}),
			),
		);
		const request: RequestEvent = {
			cached: true,
			variant: "textOp",
			active: true,
			retries: 3,
			reservationRequest: {
				reserveList: IdempotentCallable(() => emptyReserveList),
				skip: () => false,
				wait: () => Effect.succeed(false),
			},
			onFailure: () => Effect.succeed(void 0),
			onFatalError: () => Effect.succeed(void 0),
			preSend: () => Effect.succeed(void 0),
			send: (requestKey) =>
				Effect.sync(() => {
					sendAttempts += 1;
					sentKeys.push(requestKey);
				}).pipe(
					Effect.andThen(() =>
						sendAttempts === 1
							? Effect.fail(new CacheConflictException({ requestKey }))
							: Effect.succeed({ ok: true }),
					),
				),
			postSend: (data) =>
				Effect.sync(() => {
					postSendResults.push(data);
				}).pipe(Effect.mapError((err) => new FatalException({ orig: err }))),
		};

		requestManager.enqueueRequest(request);
		await Effect.runPromise(requestManager.waitFlush());

		expect(errors).toEqual([]);
		expect(sentKeys).toHaveLength(2);
		expect(sentKeys[1]).not.toBe(sentKeys[0]);
		expect(getCachedResultMock).not.toHaveBeenCalled();
		expect(postSendResults).toEqual([{ ok: true }]);
	});

	it("regenerates the request key for each cache conflict retry", async () => {
		const getCachedResultMock = vi.mocked(getCachedResultCachedCachedIdGet);
		const sentKeys: RequestKey[] = [];
		const postSendResults: unknown[] = [];
		let sendAttempts = 0;
		const requestManager = Effect.runSync(
			buildRequestManager(buildIdRepository(), () => Effect.succeed(void 0)),
		);
		const request: RequestEvent = {
			cached: true,
			variant: "textOp",
			active: true,
			retries: 3,
			reservationRequest: {
				reserveList: IdempotentCallable(() => emptyReserveList),
				skip: () => false,
				wait: () => Effect.succeed(false),
			},
			onFailure: () => Effect.succeed(void 0),
			onFatalError: () => Effect.succeed(void 0),
			preSend: () => Effect.succeed(void 0),
			send: (requestKey) =>
				Effect.sync(() => {
					sendAttempts += 1;
					sentKeys.push(requestKey);
				}).pipe(
					Effect.andThen(() =>
						sendAttempts <= 2
							? Effect.fail(new CacheConflictException({ requestKey }))
							: Effect.succeed({ ok: true }),
					),
				),
			postSend: (data) =>
				Effect.sync(() => {
					postSendResults.push(data);
				}).pipe(Effect.mapError((err) => new FatalException({ orig: err }))),
		};

		requestManager.enqueueRequest(request);
		await Effect.runPromise(requestManager.waitFlush());

		expect(sentKeys).toHaveLength(3);
		expect(new Set(sentKeys).size).toBe(3);
		expect(getCachedResultMock).not.toHaveBeenCalled();
		expect(postSendResults).toEqual([{ ok: true }]);
	});

	it("releases reserved entries after a successful request", async () => {
		const idRepo = buildIdRepository();
		const ccId = Effect.runSync(
			idRepo.newIdAndBindId({
				kind: "chapterContent",
				servId: CCServId("00000000-0000-0000-0000-000000000007"),
			}),
		);
		const reserveList: ReserveList = {
			autoLabel: [],
			autoLabelRun: [],
			chapter: [],
			chapterContent: [{ id: ccId, kind: "chapterContent", desiredState: "locked" }],
			label: [],
			labelData: [],
			labelGroup: [],
		};

		const requestManager = Effect.runSync(
			buildRequestManager(idRepo, () => Effect.succeed(void 0)),
		);
		const request: RequestEvent = {
			cached: true,
			variant: "textOp",
			active: true,
			retries: 3,
			reservationRequest: {
				reserveList: IdempotentCallable(() => reserveList),
				skip: () => false,
				wait: () => Effect.succeed(false),
			},
			onFailure: () => Effect.succeed(void 0),
			onFatalError: () => Effect.succeed(void 0),
			preSend: () => Effect.succeed(void 0),
			send: () => Effect.succeed({ ok: true }),
			postSend: () => Effect.succeed(void 0),
		};

		requestManager.enqueueRequest(request);
		await Effect.runPromise(requestManager.waitFlush());

		expect(Effect.runSync(idRepo.idObjState({ kind: "chapterContent", id: ccId }))).toBe(
			"clean",
		);
	});

	it("does not consume retries while a cached request is pending", async () => {
		vi.useFakeTimers();
		const getCachedResultMock = vi.mocked(getCachedResultCachedCachedIdGet);
		const postSendResults: unknown[] = [];
		let statusQueries = 0;
		getCachedResultMock.mockImplementation(async () => {
			statusQueries += 1;
			return {
				status: 200,
				headers: new Headers(),
				data:
					statusQueries <= 6
						? {
								status: "pending",
								status_code: null,
								response: null,
								error: null,
							}
						: {
								status: "success",
								status_code: 200,
								response: { ok: true },
								error: null,
							},
			};
		});
		const requestManager = Effect.runSync(
			buildRequestManager(buildIdRepository(), () => Effect.succeed(void 0)),
		);
		const request: RequestEvent = {
			cached: true,
			variant: "textOp",
			active: true,
			retries: 3,
			reservationRequest: {
				reserveList: IdempotentCallable(() => emptyReserveList),
				skip: () => false,
				wait: () => Effect.succeed(false),
			},
			onFailure: () => Effect.succeed(void 0),
			onFatalError: () => Effect.succeed(void 0),
			preSend: () => Effect.succeed(void 0),
			send: () => Effect.never,
			postSend: (data) =>
				Effect.sync(() => {
					postSendResults.push(data);
				}),
		};

		requestManager.enqueueRequest(request);
		const flush = Effect.runPromise(requestManager.waitFlush());
		await vi.advanceTimersByTimeAsync(10_001);
		await flush;

		expect(statusQueries).toBe(7);
		expect(postSendResults).toEqual([{ ok: true }]);
		expect(requestManager.isQueueEmpty()).toBe(true);
	});

	it("removes an exhausted request before running its failure handler", async () => {
		let failureCalls = 0;
		const requestManager = Effect.runSync(
			buildRequestManager(buildIdRepository(), () => Effect.succeed(void 0)),
		);
		const request: RequestEvent = {
			cached: true,
			variant: "textOp",
			active: true,
			retries: 0,
			reservationRequest: {
				reserveList: IdempotentCallable(() => emptyReserveList),
				skip: () => false,
				wait: () => Effect.succeed(false),
			},
			onFailure: () =>
				Effect.sync(() => {
					failureCalls += 1;
				}),
			onFatalError: () => Effect.succeed(void 0),
			preSend: () => Effect.succeed(void 0),
			send: (requestKey) => Effect.fail(new CacheConflictException({ requestKey })),
			postSend: () => Effect.succeed(void 0),
		};

		requestManager.enqueueRequest(request);
		await expect(Effect.runPromise(requestManager.waitFlush())).rejects.toBeDefined();

		expect(failureCalls).toBe(1);
		expect(requestManager.isQueueEmpty()).toBe(true);
		await Effect.runPromise(requestManager.waitFlush());
		expect(failureCalls).toBe(1);
	});
});
