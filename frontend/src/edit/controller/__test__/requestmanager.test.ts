import { beforeEach, describe, expect, it, vi } from "vitest";
import { Effect } from "effect";
import { buildRequestManager } from "../requestmanager";
import { buildIdRepository } from "../idRepository";
import { IdempotentCallable } from "../types/helperTypes";
import { CacheConflictException, FatalException } from "../types/errors";
import type { TriggerEvent } from "../types/controllerTypes";
import type { RequestEvent, RequestKey, ReserveList } from "../types/requestTypes";
import { getCachedResultCachedCachedIdGet } from "@/api/endpoints/default/default";

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
});
