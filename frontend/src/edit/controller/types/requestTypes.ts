import type { InFlightIdStatus, Kind, ProvTypes } from "./idTypes";
import { type IdempotentCallable } from "./helperTypes";
import { Brand, type Effect } from "effect";
import type {
	CacheConflictException,
	ConnectionException,
	FatalException,
	NotFoundException,
} from "./errors";
import type { UnknownException } from "effect/Cause";

/**
 * Type indicating what a request event is used for. Mainly used for logging and debugging.
 */
export type RequestVariant =
	| "addLabelGroup"
	| "addChapter"
	| "textOp"
	| "labelOp"
	| "addLabelData"
	| "reloadGroup"
	| "openChapter";

/**
 * Type representing a desired reservation of a state transition for a given id and kind.
 */
export type Reservation<K extends Kind> = {
	kind: K;
	id: ProvTypes[K];
	desiredState: InFlightIdStatus;
};

/**
 * Branded type for request keys, which are unique identifiers for requests that can be used to track and manage requests in the request manager. Branded for type safety and clarity. Should be generated using the {@link regenerateKey} function to ensure uniqueness.
 */
export type RequestKey = string & Brand.Brand<"RequestKey">;
export const RequestKey = Brand.nominal<RequestKey>();

export type ReserveList = { [K in Kind]: Reservation<K>[] };

/**
 * Type representing a request to reserve.
 */
export type ReservationRequest = {
	/**
	 * List of reservations to make for this request. Branded as an IdempotentCallable to ensure that the reservation list is not re-evaluated multiple times, which could cause unintended side effects.
	 *
	 * Implementation note: when wait() returns false, all reservations in this list should be reserveable.
	 */
	reserveList: IdempotentCallable<ReserveList>;
	/**
	 * Skip this request if this function returns true provided that wait() returns false.
	 */
	skip: () => boolean;
	/**
	 * Wait to send this request until this function returns false. If not provided, the request manager will not delay this request.
	 */
	wait: () => Effect.Effect<boolean, NotFoundException>; // we do not expect this to throw, but if it does we want to treat it as a fatal error and stop processing the request, so we allow for an unknown exception to be thrown
};

/**
 * Base parameters for a request event.
 */
export type BaseRequestEvent = {
	/**
	 * Reservation request for this request event.  See {@link ReservationRequest} for details.
	 */
	reservationRequest: ReservationRequest;
	variant: RequestVariant;
	/**
	 * Handler that will be called if the request fails after all retries. Will call before corresponding reservation is released.
	 */
	onFailure: () => Effect.Effect<void>;
	/**
	 * Handler that will be called if the request encounters a fatal error. Will be called with the error that caused the fatal error, and before corresponding reservation is released.
	 */
	onFatalError: (err: Error) => Effect.Effect<void>;
	/**
	 * The number of times the request can be retried.
	 */
	retries: number;
	/**
	 * A request is passive if one of the following conditions is satisfied:
	 * - Does not modify the backend state
	 * - Depends on the completion of another passive request.
	 *
	 * This is mainly used for lazy loading and is used by the data manager instead of the request manager. See data manager implementation for details.
	 */
	active: boolean;
};

/**
 * Type representing a set of actions that can be performed to preprocess, send a request to the backend, and postprocess the response from the backend. Generic over the error type.
 */
type Sendable<E> = {
	/**
	 * Preprocess actions to perform before sending the request.
	 */
	preSend: () => Effect.Effect<void>;
	/**
	 * Send the request to the backend and return the response. Should throw an error if the request fails.
	 */
	send: (requestKey: RequestKey) => Effect.Effect<unknown, E>;
	/**
	 * Postprocess actions to perform after receiving the response from the backend. Will be called with the response data from the backend. Should throw a FatalException if postprocessing fails.
	 */
	postSend: (data: unknown) => Effect.Effect<void, FatalException>;
};

/**
 * Represents a request that is not cached on the backend.
 */
export type NoCachedRequestEvent = BaseRequestEvent &
	Sendable<ConnectionException | FatalException> & { cached: false };

/**
 * Represents a request that is cached on the backend.
 */
export type CachedRequestEvent = BaseRequestEvent &
	Sendable<ConnectionException | CacheConflictException | FatalException> & { cached: true };

export type RequestEvent = CachedRequestEvent | NoCachedRequestEvent;

export type NoCachedKeyedRequestEvent = NoCachedRequestEvent & { requestKey: RequestKey };
export type CachedKeyedRequestEvent = CachedRequestEvent & { requestKey: RequestKey };
/**
 * Keyed request event, which is a request event with a unique request key. Mainly used for tracking requests in the request manager.
 */
export type KeyedRequestEvent = NoCachedKeyedRequestEvent | CachedKeyedRequestEvent;

/**
 * Regenerates a unique request key for the given request.
 */
export const regenerateKey = <T extends BaseRequestEvent>(request: T) => {
	return { ...request, requestKey: crypto.randomUUID() };
};

/**
 * Consumes a retry attempt from the given request.
 */
export const consumeRetry = <T extends BaseRequestEvent>(request: T) => {
	return { ...request, retries: request.retries - 1 };
};

/**
 * Interface for a request manager. The request manager manages the queue of requests to be sent to the backend, and provides an interface for enqueuing requests, starting the request processing, and attaching triggers for request completion and errors. The request manager is responsible for ensuring the following invariants:
 * - If request A is enqueued before request B, there exists some resource R that both A and B depend on, and the corresponding reservations are incompatible, then A will be sent before B.
 * - For any request event, exactly one of the following functions will complete successfully: onFailure, onFatalError, or the postSend function if the request is successful.
 */
export type RequestManager = {
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
	start: () => Effect.Effect<void, UnknownException>;
	/**
	 * Lock and wait until all requests are finished. Effectively shuts down the request manager.
	 */
	waitFlush: () => Effect.Effect<void, UnknownException>; // await flush queue
};
