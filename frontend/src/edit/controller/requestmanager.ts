import { createLogger } from "@/lib/logging";

import {
	consumeRetry,
	generateRequestKey,
	regenerateKey,
	type AnyReservation,
	type CachedKeyedRequestEvent,
	type KeyedRequestEvent,
	type RequestEvent,
	type RequestManager,
} from "./types/requestTypes";
import { kinds, type IDRepository, type Kind } from "./types/idTypes";
import type { TriggerEvent } from "./types/controllerTypes";
import { Effect, Either } from "effect";
import { getCachedResultCachedCachedIdGet } from "@/api/endpoints/default/default";
import {
	CacheConflictException,
	ConnectionException,
	FatalException,
	NoCacheEntryException,
	NotFoundException,
	PendingException,
	type AnyError,
} from "./types/errors";
import { UnknownException } from "effect/Cause";
import { forEachKind, isAllReserveable } from "./types/helperTypes";

const logger = createLogger("RequestManager");
const REQUEST_LOOP_INTERVAL_MS = 500;
const STATUS_POLL_DELAYS_MS: readonly number[] = [1_000, 2_000, 4_000];
const MAX_STATUS_POLL_DELAY_MS = 5_000;

type ScheduledStatusQuery = {
	request: CachedKeyedRequestEvent;
	pendingPolls: number;
	nextPollAt: number;
};

const statusPollDelay = (pendingPolls: number): number =>
	STATUS_POLL_DELAYS_MS[pendingPolls] ?? MAX_STATUS_POLL_DELAY_MS;

/**
 * Below is a brief outline of the behaviour of the request manager.
 *
 * Each request stored in the request manager can be in one of the following three states:
 * - queued: the request is waiting to be sent/has not been sent yet
 * - unknown: the request has been sent, but we do not yet know the status of the request on the server
 * - retry: the request has been sent and we know it failed due to a recoverable error (e.g. cache conflict), and it is waiting to be retried
 *
 * Note that there are two methods to send requests to the server: send an actual request, or send a status query on a request. The former is used for requests in the queued/retry states, while the latter is used for requests in the unknown state.
 *
 * Upon request success, the request is removed from the control of the request manager. For convenience we denote this state by resolved.
 * Upon an unrecoverable failure, the request manager will populate the errors state using the injected setErrors function. The controller will then decide what to do with the failed requests (most likely force a reload). For convenience we denote this state by failed.
 *
 * We separate errors into 3 categories:
 * - Timeout errors - errors where we send an HTTP request but do not receive a response. Can occur due to connection issues or network latency
 * - Cache errors - errors where we receive a cache conflict response from the server (i.e. request key already in use) or a no cache entry response from the server.
 * - Fatal error - everything else (i.e. sent to backend and received some bad data response)
 *
 * Requests can transition according to the following rules:
 *
 * - any state -> success: when the request is sent and we receive a success response from the server
 * - any state -> failure: when the request is sent and we receive a fatal error response from the server
 * - any state -> unknown: when the request is sent and we receive a timeout error
 * - unknown -> unknown: when a status query confirms that the request is still pending
 * - any state -> retry: when the request is sent and we receive a cache conflict error or a no cache entry error
 *
 * For each request event we keep track of a request key and a retry count. This applies to each of the states above. Each event is sent to the server along with its request key.
 * Each recoverable request failure decreases its retry count. If the retry count hits <0, the request is considered failed and will transition to the failed state. A successful status query that reports the request is still pending does not consume a retry.
 * Whenever a request transitions to the retry state, its request key will be regenerated.
 *
 * Below is the general execution flow.
 *
 * 1. User events are placed into a queue of events.
 * 2. Upon certain event triggers (e.g. after a debounce period with no new events), the request manager selects new events to be sent to the server according to the following algorithm:
 *      From queued state:
 *      - while the request queue is nonempty and the front request in the queue is reserveable (see IdRepository for what reserveable means):
 *          - remove the front request from the queue and place it into a list of outgoing requests
 *          - reserve the provisional ids corresponding to the event
 *      If any event from the unknown/retry states has retry count <0, immediately throw a fatal error.
 *      For each unknown event, ping the server for the status of the request using the request key.
 *      For each retry event, send a full request.
 * 3. Aggregate all events and sent them to the server along with their request keys.
 * 4. Receive the responses/errors from all the events and do the following:
 *      - For each successful event (no matter which state), free the corresponding provisional ids corresponding to that request event.
 *      - For each failed event (no matter which state)
 *          - Decrement the corresponding retry count, unless the status query successfully reported that the request is still pending.
 *          - If the error was a cache conflict, regenerate the request key.
 *          - Move the event to the corresponding state.
 *         - Continue holding the provisional ids for the event.
 * 5. Repeat steps 1-4 until there are no more recorded request events left.
 *
 * Notes:
 * - The only edge case the author can think of at the moment is if a request is sent and received by the server, a cache conflict occurs, but the response from the server is lost due to connection issues. In this case, the request manager will place the request in the unknown state instead of the retry state. When the request manager pings the server about the status, it will see another request with the same key that has succeeded, when it should have retried the request. This leaves the frontend in an inconsistent state (if an error response was received instead, the frontend will see a fatal error and refresh). However, this is a very unlikely noncritical edge case and we will put off fixing it for now. Furthermore, we can mitigate this issue by making the request keys more collision resistant.
 */

export const buildRequestManager = (
	idRepo: IDRepository,
	raiseTriggerEvent: (event: TriggerEvent) => Effect.Effect<void>,
): Effect.Effect<RequestManager> =>
	Effect.gen(function* () {
		const requestQueue: KeyedRequestEvent[] = [];
		const statusQueries: ScheduledStatusQuery[] = []; // requests for which we have sent the main request and are now polling for their status
		const retryRequests: KeyedRequestEvent[] = []; // requests that have failed due to cache conflicts/known recoverable errors and should be retried
		const sendMut = yield* Effect.makeSemaphore(1);
		const debounceLatch = yield* Effect.makeLatch(true);

		let shuttingDown: boolean = false;

		const isQueueEmpty = () =>
			requestQueue.length === 0 && statusQueries.length === 0 && retryRequests.length === 0;

		const enqueueRequest = (request: RequestEvent) => {
			if (shuttingDown) return;
			console.log("enqueueRequest", request.variant);
			requestQueue.push({ ...request, requestKey: generateRequestKey() });
		};

		const requestStatusQuery = (request: CachedKeyedRequestEvent) =>
			Effect.gen(function* () {
				const response = yield* Effect.tryPromise({
					try: () => getCachedResultCachedCachedIdGet(request.requestKey),
					catch: (err) => {
						logger.error(`Failed to fetch status for request ${request.requestKey}`, {
							error: err instanceof Error ? err : new UnknownException(String(err)),
						});
						return new ConnectionException({ orig: err });
					},
				});
				if (response.status === 404) {
					return yield* Effect.fail(
						new NoCacheEntryException({ requestKey: request.requestKey }),
					);
				} else if (response.status === 422) {
					return yield* Effect.fail(new FatalException({ orig: response }));
				} else {
					if (response.data.error && response.data.error.cacheConflict) {
						return yield* Effect.fail(
							new CacheConflictException({ requestKey: request.requestKey }),
						);
					} else if (response.data.error) {
						return yield* Effect.fail(new FatalException({ orig: response }));
					} else if (response.data.status === "failure") {
						return yield* Effect.fail(new FatalException({ orig: response }));
					} else if (response.data.status === "pending") {
						return yield* Effect.fail(new PendingException());
					} else {
						return response.data.response;
					}
				}
			});

		const reserveAction = (
			request: KeyedRequestEvent,
		): Effect.Effect<"wait" | "skip" | "reserve", NotFoundException> =>
			Effect.gen(function* () {
				if (request.reservationRequest.skip()) {
					return yield* Effect.succeed("skip" as const);
				} else if (yield* request.reservationRequest.wait()) {
					return yield* Effect.succeed("wait" as const);
				}
				const reserveList = request.reservationRequest.reserveList();
				return yield* isAllReserveable(idRepo, reserveList).pipe(
					Effect.map((a) => (a ? ("reserve" as const) : ("wait" as const))),
				);
			});

		const send = () =>
			Effect.gen(function* () {
				let madeProgress = false;
				const qLen = requestQueue.length + statusQueries.length + retryRequests.length;
				if (qLen > 0) {
					console.log("send() starting, queue=%d", requestQueue.length);
				}
				const fromQueueRequests: KeyedRequestEvent[] = [];

				const limitExceeded: KeyedRequestEvent[] = [];
				for (let index = statusQueries.length - 1; index >= 0; index -= 1) {
					const request = statusQueries[index].request;
					if (request.retries >= 0) continue;
					statusQueries.splice(index, 1);
					const reserveList = request.reservationRequest.reserveList();
					yield* forEachKind(
						reserveList,
						(reservation: AnyReservation<Kind>) =>
							idRepo.releaseIdObjStateOnFailure(reservation),
						kinds,
					);
					yield* request.onFailure();
					logger.error(
						`Request ${request.requestKey} has exceeded the maximum number of retries`,
						{
							request: request,
						},
					);
					limitExceeded.push(request);
				}
				for (let index = retryRequests.length - 1; index >= 0; index -= 1) {
					const request = retryRequests[index];
					if (request.retries >= 0) continue;
					retryRequests.splice(index, 1);
					const reserveList = request.reservationRequest.reserveList();
					yield* forEachKind(
						reserveList,
						(reservation: AnyReservation<Kind>) =>
							idRepo.releaseIdObjStateOnFailure(reservation),
						kinds,
					);
					yield* request.onFailure();
					logger.error(
						`Request ${request.requestKey} has exceeded the maximum number of retries`,
						{
							request: request,
						},
					);
					limitExceeded.push(request);
				}
				if (limitExceeded.length > 0) {
					return yield* Effect.fail(
						new UnknownException(
							`${limitExceeded.length} requests have exceeded the maximum number of retries`,
						),
					);
				}
				while (requestQueue.length > 0) {
					const action = yield* reserveAction(requestQueue[0]);
					console.log(
						"reserveAction: variant=%s action=%s",
						requestQueue[0].variant,
						action,
					);
					if (action === "wait") {
						break;
					}
					const request = requestQueue.shift()!;
					madeProgress = true;
					if (action === "skip") {
						continue;
					}
					const reservationRequest = request.reservationRequest;
					const reserveList = reservationRequest.reserveList();
					yield* forEachKind(
						reserveList,
						(reservation: AnyReservation<Kind>) =>
							idRepo.reserveIdObjState(reservation),
						kinds,
					);
					yield* request.preSend();
					fromQueueRequests.push(request);
				}

				const now = Date.now();
				const dueStatusQueries: ScheduledStatusQuery[] = [];
				for (let index = statusQueries.length - 1; index >= 0; index -= 1) {
					if (statusQueries[index].nextPollAt > now) continue;
					dueStatusQueries.push(statusQueries[index]);
					statusQueries.splice(index, 1);
					madeProgress = true;
				}
				const pendingPollsByRequestKey = new Map(
					dueStatusQueries.map(({ request, pendingPolls }) => [
						request.requestKey,
						pendingPolls,
					]),
				);

				const sem = yield* Effect.makeSemaphore(10);
				const handleReturn = <T, E>(request: KeyedRequestEvent) =>
					Effect.mapBoth({
						onFailure: (error: E): { error: E; request: KeyedRequestEvent } => ({
							error,
							request,
						}),
						onSuccess: (value: T) => ({ value, request }),
					});

				const fromQueueEffect = Effect.partition(
					fromQueueRequests,
					(requestEvent) => {
						console.log(
							"firing request",
							requestEvent.variant,
							requestEvent.requestKey,
						);
						return sem
							.withPermits(1)(requestEvent.send(requestEvent.requestKey))
							.pipe(Effect.timeout("10 seconds"))
							.pipe(handleReturn(requestEvent));
					},
					{ concurrency: "unbounded" },
				);
				const statusQueriesEffect = Effect.partition(
					dueStatusQueries,
					({ request }) =>
						sem
							.withPermits(1)(requestStatusQuery(request))
							.pipe(Effect.timeout("10 seconds"))
							.pipe(handleReturn(request)),
					{ concurrency: "unbounded" },
				);

				const retryRequestsEffect = Effect.partition(
					retryRequests,
					(requestEvent) =>
						sem
							.withPermits(1)(requestEvent.send(requestEvent.requestKey))
							.pipe(Effect.timeout("10 seconds"))
							.pipe(handleReturn(requestEvent)),
					{ concurrency: "unbounded" },
				);
				if (retryRequests.length > 0) {
					madeProgress = true;
				}

				const [
					[fromQueueResultFail, fromQueueResultPass],
					[statusQueryResultFail, statusQueryResultPass],
					[retryResultFail, retryResultPass],
				] = yield* Effect.all([fromQueueEffect, statusQueriesEffect, retryRequestsEffect], {
					concurrency: "unbounded",
				});
				const totalResults =
					fromQueueResultPass.length +
					fromQueueResultFail.length +
					statusQueryResultPass.length +
					statusQueryResultFail.length +
					retryResultPass.length +
					retryResultFail.length;
				if (totalResults > 0) {
					console.log(
						"send() results: fromQueue pass=%d fail=%d statusQuery pass=%d fail=%d retry pass=%d fail=%d",
						fromQueueResultPass.length,
						fromQueueResultFail.length,
						statusQueryResultPass.length,
						statusQueryResultFail.length,
						retryResultPass.length,
						retryResultFail.length,
					);
				}

				const fatalFailedRequests: { error: AnyError; request: KeyedRequestEvent }[] = [];
				const newStatusQueries: ScheduledStatusQuery[] = [];
				const newRetryRequests: KeyedRequestEvent[] = [];
				const scheduleStatusQuery = (
					request: CachedKeyedRequestEvent,
					pendingPolls: number,
				) => {
					newStatusQueries.push({
						request,
						pendingPolls,
						nextPollAt: Date.now() + statusPollDelay(pendingPolls),
					});
				};

				const requeueRequest = (result: {
					error: AnyError;
					request: KeyedRequestEvent;
				}) => {
					if (result.request.cached && result.error._tag === "PendingException") {
						const pendingPolls =
							(pendingPollsByRequestKey.get(result.request.requestKey) ?? 0) + 1;
						scheduleStatusQuery(result.request, pendingPolls);
					} else if (result.request.cached && result.error._tag === "TimeoutException") {
						const newRequest = consumeRetry(result.request);
						const pendingPolls =
							pendingPollsByRequestKey.get(result.request.requestKey) ?? 0;
						scheduleStatusQuery(newRequest, pendingPolls);
					} else {
						const newRequest = consumeRetry(result.request);
						if (result.error._tag === "CacheConflictException") {
							newRetryRequests.push(regenerateKey(newRequest));
						} else if (result.error._tag === "ConnectionException") {
							newRetryRequests.push(newRequest);
						} else if (result.error._tag === "TimeoutException") {
							newRetryRequests.push(regenerateKey(newRequest));
						} else if (result.error._tag === "NoCacheEntryException") {
							newRetryRequests.push(regenerateKey(newRequest));
						} else {
							fatalFailedRequests.push(result);
						}
					}
				};

				for (const result of [
					...fromQueueResultFail,
					...statusQueryResultFail,
					...retryResultFail,
				]) {
					requeueRequest(result);
				}

				const postSendResult = yield* Effect.forEach(
					[...statusQueryResultPass, ...retryResultPass, ...fromQueueResultPass],
					({ value, request }) =>
						Effect.either(
							request.postSend(value).pipe(
								Effect.mapBoth({
									onFailure: (err) => ({ error: err, request }),
									onSuccess: () => request,
								}),
							),
						),
				);
				for (const result of postSendResult) {
					if (Either.isLeft(result)) {
						fatalFailedRequests.push(result.left);
					} else {
						const request = result.right;
						const reserveList = request.reservationRequest.reserveList();
						yield* forEachKind(
							reserveList,
							(reservation: AnyReservation<Kind>) =>
								idRepo.releaseIdObjStateOnSuccess(reservation),
							kinds,
						);
					}
				}
				if (fatalFailedRequests.length > 0) {
					for (const { request, error } of fatalFailedRequests) {
						yield* request.onFatalError(error);
						const reserveList = request.reservationRequest.reserveList();
						yield* forEachKind(
							reserveList,
							(reservation: AnyReservation<Kind>) =>
								idRepo.releaseIdObjStateOnFailure(reservation),
							kinds,
						);
					}
					yield* raiseTriggerEvent({
						eventType: "errorOccured",
						from: "requestManager",
						data: fatalFailedRequests,
					});
					return yield* Effect.fail(
						new UnknownException(
							`${fatalFailedRequests.length} requests failed fatally`,
						),
					);
				}
				retryRequests.length = 0; // empty the array
				retryRequests.push(...newRetryRequests);
				statusQueries.push(...newStatusQueries);
				return madeProgress;
			});

		const sendLoop = () =>
			Effect.forever(
				Effect.gen(function* () {
					const total = requestQueue.length + statusQueries.length + retryRequests.length;
					if (total > 0) {
						console.log(
							"sendLoop: queue=%d status=%d retry=%d",
							requestQueue.length,
							statusQueries.length,
							retryRequests.length,
						);
					}
					yield* sendMut
						.withPermits(1)(send())
						.pipe(
							Effect.catchAll(() => Effect.sleep("1 second")),
							Effect.andThen(() => Effect.sleep(REQUEST_LOOP_INTERVAL_MS)),
						);
				}),
			);

		const start = (): Effect.Effect<void, UnknownException> => {
			console.log("requestManager.start forking sendLoop");
			return Effect.fork(sendLoop()).pipe(
				Effect.mapError((err) => new UnknownException(String(err))),
				Effect.andThen(() => Effect.succeed(void 0)),
			);
		};

		const debounce = () =>
			Effect.gen(function* () {
				yield* Effect.fork(
					debounceLatch.close
						.pipe(Effect.andThen(Effect.sleep("0.5 seconds")))
						.pipe(Effect.andThen(debounceLatch.open)),
				);
				yield* Effect.sleep("0.1 seconds"); // wait for thread to start
			});

		const waitFlush = (): Effect.Effect<void, UnknownException> =>
			Effect.gen(function* () {
				shuttingDown = true;
				while (!isQueueEmpty()) {
					const madeProgress = yield* sendMut
						.withPermits(1)(send())
						.pipe(Effect.mapError((err) => new UnknownException(String(err))));
					if (!isQueueEmpty() && !madeProgress) {
						yield* Effect.sleep(REQUEST_LOOP_INTERVAL_MS);
					}
				}
			});

		return {
			isQueueEmpty,
			enqueueRequest,
			debounce,
			start,
			waitFlush,
		};
	});
