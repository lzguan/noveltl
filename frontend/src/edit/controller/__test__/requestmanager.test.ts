import { beforeEach, describe, expect, it, vi } from "vitest";
import { Effect } from "effect";
import { buildRequestManager } from "../requestmanager";
import { buildIdRepository } from "../idRepository";
import { IdempotentCallable } from "../types/helperTypes";
import {
	CacheConflictException,
	FatalException,
} from "../types/errors";
import type { TriggerEvent } from "../types/controllerTypes";
import type { RequestEvent, RequestKey, ReserveList } from "../types/requestTypes";
import { getCachedResultCachedCachedIdGet } from "@/api/endpoints/default/default";
import { CacheEntryStatus } from "@/api/models/cacheEntryStatus";

vi.mock("@/api/endpoints/default/default", async (importOriginal) => {
	const actual = await importOriginal<typeof import("@/api/endpoints/default/default")>();
	return {
		...actual,
		getCachedResultCachedCachedIdGet: vi.fn(),
	};
});

const emptyReserveList: ReserveList = {
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

	it("polls cached request status after a cached cache conflict", async () => {
		const getCachedResultMock = vi.mocked(getCachedResultCachedCachedIdGet);
		getCachedResultMock.mockResolvedValue({
			status: 200,
			data: {
				status: CacheEntryStatus.success,
				status_code: 200,
				response: { ok: true },
				error: null,
			},
			headers: new Headers(),
		});
		const sentKeys: RequestKey[] = [];
		const postSendResults: unknown[] = [];
		const errors: TriggerEvent[] = [];
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
					sentKeys.push(requestKey);
				}).pipe(
					Effect.andThen(
						Effect.fail(new CacheConflictException({ requestKey })),
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
		expect(sentKeys).toHaveLength(1);
		expect(getCachedResultMock).toHaveBeenCalledWith(sentKeys[0]);
		expect(postSendResults).toEqual([{ ok: true }]);
	});

	it("keeps polling cached request status while the backend reports pending", async () => {
		const getCachedResultMock = vi.mocked(getCachedResultCachedCachedIdGet);
		getCachedResultMock
			.mockResolvedValueOnce({
				status: 200,
				data: {
					status: CacheEntryStatus.pending,
					status_code: null,
					response: null,
					error: null,
				},
				headers: new Headers(),
			})
			.mockResolvedValueOnce({
				status: 200,
				data: {
					status: CacheEntryStatus.success,
					status_code: 200,
					response: { ok: true },
					error: null,
				},
				headers: new Headers(),
			});
		const sentKeys: RequestKey[] = [];
		const postSendResults: unknown[] = [];
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
					sentKeys.push(requestKey);
				}).pipe(
					Effect.andThen(
						Effect.fail(new CacheConflictException({ requestKey })),
					),
				),
			postSend: (data) =>
				Effect.sync(() => {
					postSendResults.push(data);
				}).pipe(Effect.mapError((err) => new FatalException({ orig: err }))),
		};

		requestManager.enqueueRequest(request);
		await Effect.runPromise(requestManager.waitFlush());

		expect(sentKeys).toHaveLength(1);
		expect(getCachedResultMock).toHaveBeenCalledTimes(2);
		expect(getCachedResultMock).toHaveBeenNthCalledWith(1, sentKeys[0]);
		expect(getCachedResultMock).toHaveBeenNthCalledWith(2, sentKeys[0]);
		expect(postSendResults).toEqual([{ ok: true }]);
	});
});
