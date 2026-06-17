import { createLogger } from "@/lib/logging";

import {
	consumeRetry,
	regenerateKey,
	RequestKey,
	type CachedKeyedRequestEvent,
	type KeyedRequestEvent,
	type RequestEvent,
	type RequestManager,
} from "./types/requestTypes";
import type { IDRepository } from "./types/idTypes";
import type { TriggerEvent } from "./types/controllerTypes";
import { Effect, Either, Fiber } from "effect";
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

const logger = createLogger("RequestManager");

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
 * - any state -> retry: when the request is sent and we receive a cache conflict error or a no cache entry error
 *
 * For each request event we keep track of a request key and a retry count. This applies to each of the states above. Each event is sent to the server along with its request key.
 * Each time a request is sent to the server, its retry count decreases. If the retry count hits <0, the request is considered failed and will transition to the failed state.
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
 *          - Decrement the corresponding retry count.
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
): Effect.Effect<RequestManager<TriggerEvent>> =>
	Effect.gen(function* () {
		const requestQueue: KeyedRequestEvent[] = [];
		const statusQueries: CachedKeyedRequestEvent[] = []; // requests for which we have sent the main request and are now polling for their status
		const retryRequests: KeyedRequestEvent[] = []; // requests that have failed due to cache conflicts/known recoverable errors and should be retried
		const startedMut = yield* Effect.makeSemaphore(1);

		let debounceLock: boolean = false; // if true do not send any requests to server
		let shuttingDown: boolean = false;
		let debounceFiber: Fiber.Fiber<void> | null = null;

		let raiseTriggerEvent: (event: TriggerEvent) => void = () => {};

		const attachTrigger = (raise: (event: TriggerEvent) => void) => {
			raiseTriggerEvent = raise;
		};

		const detachTrigger = () => {
			raiseTriggerEvent = () => {};
		};

		const isQueueEmpty = () =>
			requestQueue.length === 0 && statusQueries.length === 0 && retryRequests.length === 0;

		const enqueueRequest = (request: RequestEvent) => {
			if (shuttingDown) return;
			requestQueue.push({ ...request, requestKey: RequestKey(crypto.randomUUID()), retries: 3 });
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
					return yield* Effect.fail(new NoCacheEntryException({ requestKey: request.requestKey }));
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
					return yield* Effect.succeed("skip" as "skip");
				} else if (yield* request.reservationRequest.wait()) {
					return yield* Effect.succeed("wait" as "wait");
				}
				const reserveList = request.reservationRequest.reserveList();
				const results = Effect.all([
					Effect.forEach(reserveList.chapter, (reservation) =>
						idRepo.isReserveable(reservation.kind, reservation.id, reservation.desiredState),
					),
					Effect.forEach(reserveList.label, (reservation) =>
						idRepo.isReserveable(reservation.kind, reservation.id, reservation.desiredState),
					),
					Effect.forEach(reserveList.labelData, (reservation) =>
						idRepo.isReserveable(reservation.kind, reservation.id, reservation.desiredState),
					),
					Effect.forEach(reserveList.labelGroup, (reservation) =>
						idRepo.isReserveable(reservation.kind, reservation.id, reservation.desiredState),
					),
					Effect.forEach(reserveList.chapterContent, (reservation) =>
						idRepo.isReserveable(reservation.kind, reservation.id, reservation.desiredState),
					),
				]);

				const allResults = yield* results;
				return yield* allResults.flatMap((val) => val).every((isReserveable) => isReserveable)
					? Effect.succeed("reserve" as "reserve")
					: Effect.succeed("wait" as "wait");
			});

		const send = () =>
			Effect.gen(function* () {
				const fromQueueRequests: KeyedRequestEvent[] = [];

				let delay: number = 1000; // todo: implement exponential backoff for retries instead of fixed delay

				const limitExceeded: KeyedRequestEvent[] = [];
				for (const request of [...statusQueries, ...retryRequests]) {
					if (request.retries < 0) {
						const reserveList = request.reservationRequest.reserveList();
						yield* Effect.forEach(reserveList.chapter, (reservation) =>
							idRepo.releaseIdObjStateOnFailure(reservation.kind, reservation.id),
						);
						yield* Effect.forEach(reserveList.label, (reservation) =>
							idRepo.releaseIdObjStateOnFailure(reservation.kind, reservation.id),
						);
						yield* Effect.forEach(reserveList.labelData, (reservation) =>
							idRepo.releaseIdObjStateOnFailure(reservation.kind, reservation.id),
						);
						yield* Effect.forEach(reserveList.labelGroup, (reservation) =>
							idRepo.releaseIdObjStateOnFailure(reservation.kind, reservation.id),
						);
						yield* Effect.forEach(reserveList.chapterContent, (reservation) =>
							idRepo.releaseIdObjStateOnFailure(reservation.kind, reservation.id),
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
					if (action === "wait") {
						break;
					}
					const request = requestQueue.shift()!;
					if (action === "skip") {
						continue;
					}
					const reservationRequest = request.reservationRequest;
					const reserveList = reservationRequest.reserveList();
					yield* Effect.forEach(reserveList.chapter, (reservation) =>
						idRepo.reserveIdObjState(reservation.kind, reservation.id, reservation.desiredState),
					);
					yield* Effect.forEach(reserveList.label, (reservation) =>
						idRepo.reserveIdObjState(reservation.kind, reservation.id, reservation.desiredState),
					);
					yield* Effect.forEach(reserveList.labelData, (reservation) =>
						idRepo.reserveIdObjState(reservation.kind, reservation.id, reservation.desiredState),
					);
					yield* Effect.forEach(reserveList.labelGroup, (reservation) =>
						idRepo.reserveIdObjState(reservation.kind, reservation.id, reservation.desiredState),
					);
					yield* Effect.forEach(reserveList.chapterContent, (reservation) =>
						idRepo.reserveIdObjState(reservation.kind, reservation.id, reservation.desiredState),
					);
					yield* request.preSend();
					fromQueueRequests.push(request);
				}

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
					(requestEvent) =>
						sem
							.withPermits(1)(requestEvent.send(requestEvent.requestKey))
							.pipe(Effect.timeout("10 seconds"))
							.pipe(handleReturn(requestEvent)),
					{ concurrency: "unbounded" },
				);
				const statusQueriesEffect = Effect.partition(
					statusQueries,
					(requestEvent) =>
						sem
							.withPermits(1)(requestStatusQuery(requestEvent))
							.pipe(Effect.timeout("10 seconds"))
							.pipe(handleReturn(requestEvent)),
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

				const [
					[fromQueueResultFail, fromQueueResultPass],
					[statusQueryResultFail, statusQueryResultPass],
					[retryResultFail, retryResultPass],
				] = yield* Effect.all([fromQueueEffect, statusQueriesEffect, retryRequestsEffect], {
					concurrency: "unbounded",
				});

				const fatalFailedRequests: { error: AnyError; request: KeyedRequestEvent }[] = [];
				const otherFailedRequests: { error: AnyError; request: KeyedRequestEvent }[] = [];

				const newStatusQueries: CachedKeyedRequestEvent[] = [];
				const newRetryRequests: KeyedRequestEvent[] = [];

				const requeueRequest = (result: { error: AnyError; request: KeyedRequestEvent }) => {
					if (
						result.request.cached &&
						(result.error._tag === "TimeoutException" || result.error._tag === "PendingException")
					) {
						const newRequest = consumeRetry(result.request);
						newStatusQueries.push(newRequest);
						otherFailedRequests.push(result);
					} else {
						const newRequest = consumeRetry(result.request);
						if (result.error._tag === "CacheConflictException") {
							newRetryRequests.push(regenerateKey(newRequest));
							otherFailedRequests.push(result);
						} else if (result.error._tag === "ConnectionException") {
							newRetryRequests.push(newRequest);
							otherFailedRequests.push(result);
						} else if (result.error._tag === "TimeoutException") {
							newRetryRequests.push(regenerateKey(newRequest));
							otherFailedRequests.push(result);
						} else if (result.error._tag === "NoCacheEntryException") {
							newRetryRequests.push(regenerateKey(newRequest));
							otherFailedRequests.push(result);
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
						yield* Effect.forEach(reserveList.chapter, (reservation) =>
							idRepo.releaseIdObjStateOnSuccess(reservation.kind, reservation.id),
						);
						yield* Effect.forEach(reserveList.label, (reservation) =>
							idRepo.releaseIdObjStateOnSuccess(reservation.kind, reservation.id),
						);
						yield* Effect.forEach(reserveList.labelData, (reservation) =>
							idRepo.releaseIdObjStateOnSuccess(reservation.kind, reservation.id),
						);
						yield* Effect.forEach(reserveList.labelGroup, (reservation) =>
							idRepo.releaseIdObjStateOnSuccess(reservation.kind, reservation.id),
						);
						yield* Effect.forEach(reserveList.chapterContent, (reservation) =>
							idRepo.releaseIdObjStateOnSuccess(reservation.kind, reservation.id),
						);
					}
				}
				if (fatalFailedRequests.length > 0) {
					for (const { request, error } of fatalFailedRequests) {
						yield* request.onFatalError(error);
						const reserveList = request.reservationRequest.reserveList();
						yield* Effect.forEach(reserveList.chapter, (reservation) =>
							idRepo.releaseIdObjStateOnFailure(reservation.kind, reservation.id),
						);
						yield* Effect.forEach(reserveList.label, (reservation) =>
							idRepo.releaseIdObjStateOnFailure(reservation.kind, reservation.id),
						);
						yield* Effect.forEach(reserveList.labelData, (reservation) =>
							idRepo.releaseIdObjStateOnFailure(reservation.kind, reservation.id),
						);
						yield* Effect.forEach(reserveList.labelGroup, (reservation) =>
							idRepo.releaseIdObjStateOnFailure(reservation.kind, reservation.id),
						);
						yield* Effect.forEach(reserveList.chapterContent, (reservation) =>
							idRepo.releaseIdObjStateOnFailure(reservation.kind, reservation.id),
						);
					}
					raiseTriggerEvent({
						eventType: "errorOccured",
						from: "requestManager",
						data: fatalFailedRequests,
					});
					return yield* Effect.fail(
						new UnknownException(`${fatalFailedRequests.length} requests failed fatally`),
					);
				}
				retryRequests.length = 0; // empty the array
				statusQueries.length = 0;
				retryRequests.push(...newRetryRequests);
				statusQueries.push(...newStatusQueries);

				return delay;
			});
		const sendLoop = Effect.gen(function* () {
			while (!isQueueEmpty()) {
				if (debounceLock) {
					yield* Effect.sleep(100);
				} else {
					const delay = yield* send();
					yield* Effect.sleep(delay);
				}
			}
		}).pipe(
			Effect.mapError((err) => {
				if (err._tag === "UnknownException") {
					return err;
				}
				return new UnknownException(String(err));
			}),
		);

		const start = (): Effect.Effect<void, UnknownException> => startedMut.withPermits(1)(sendLoop);

		const debounce = () =>
			Effect.gen(function* () {
				debounceLock = true;
				if (debounceFiber) yield* Fiber.interrupt(debounceFiber);
				debounceFiber = yield* Effect.fork(
					Effect.sleep(1000).pipe(
						Effect.tap(() => {
							debounceLock = false;
							debounceFiber = null;
						}),
					),
				);
			});

		const waitFlush = (): Effect.Effect<void, UnknownException> =>
			Effect.gen(function* () {
				shuttingDown = true;
				yield* startedMut.withPermits(1)(sendLoop);
			});

		return {
			isQueueEmpty,
			enqueueRequest,
			debounce,
			start,
			waitFlush,
			attachTrigger,
			detachTrigger,
		};
	});
