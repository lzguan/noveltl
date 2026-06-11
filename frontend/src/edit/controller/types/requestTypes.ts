import type { InFlightIdStatus, Kind, ProvId } from "./idTypes";
import { type IdempotentCallable } from "./helperTypes";
import { Brand, type Effect } from "effect";
import type { CacheConflictException, ConnectionException, FatalException } from "./errors";

export type RequestVariant =
	| "addLabelGroup"
	| "textOp"
	| "labelOp"
	| "addLabelData"
	| "reloadGroup";

export type Reservation = {
	kind: Kind;
	id: ProvId;
	desiredState: InFlightIdStatus;
};

export type RequestKey = string & Brand.Brand<"RequestKey">;

export const RequestKey = Brand.nominal<RequestKey>();

export type ReservationRequest = {
	reserveList: IdempotentCallable<Reservation[]>;
	/**
	 * Skip this request if this function returns true provided that wait() returns false.
	 */
	skip: () => boolean;
	/**
	 * Wait to send this request until this function returns false. If not provided, the request manager will not delay this request.
	 */
	wait: () => boolean;
};

export type BaseRequestEvent = {
	reservationRequest: ReservationRequest;
	variant: RequestVariant;
	onFailure: () => void; // handler that will be called if the request fails after all retries, with the error that caused the failure
	onFatalError: (err: Error) => void; // handler that will be called if the request encounters a fatal error
	retries: number;
	active: boolean;
};

type Sendable<E> = {
	preSend: () => void;
	send: (requestKey: RequestKey) => Effect.Effect<unknown, E>;
	postSend: (data: unknown) => Effect.Effect<void, FatalException>;
};

export type NoCachedRequestEvent = BaseRequestEvent &
	Sendable<ConnectionException | FatalException> & { cached: false };

export type CachedRequestEvent = BaseRequestEvent &
	Sendable<ConnectionException | CacheConflictException | FatalException> & { cached: true };

export type RequestEvent = CachedRequestEvent | NoCachedRequestEvent;

export type NoCachedKeyedRequestEvent = NoCachedRequestEvent & { requestKey: RequestKey };
export type CachedKeyedRequestEvent = CachedRequestEvent & { requestKey: RequestKey };

export type KeyedRequestEvent = NoCachedKeyedRequestEvent | CachedKeyedRequestEvent;

export const regenerateKey = <T extends BaseRequestEvent>(request: T) => {
	return { ...request, requestKey: crypto.randomUUID() };
};

export const consumeRetry = <T extends BaseRequestEvent>(request: T) => {
	return { ...request, retries: request.retries - 1 };
};

export type RequestManager<TriggerEventT> = {
	/**
	 * Returns true if there are no unfinished requests.
	 */
	isQueueEmpty: () => boolean;
	/**
	 * Enqueue a single request event.
	 */
	enqueueRequest: (request: RequestEvent) => void;

	/**
	 * Debounce the request queue.
	 */
	debounce: () => Effect.Effect<void>;
	/**
	 * Send requests until the queue is empty.
	 */
	start: () => Effect.Effect<void, Error>;
	/**
	 * Lock and wait until all requests are finished.
	 */
	waitFlush: () => Effect.Effect<void, Error>; // await flush queue

	/**
	 * Attach a trigger function.
	 */
	attachTrigger: (trigger: (t: TriggerEventT) => void) => void;
	/**
	 * Detach the trigger function.
	 */
	detachTrigger: () => void;
};
