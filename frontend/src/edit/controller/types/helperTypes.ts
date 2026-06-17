import type { IDRepository } from "./idTypes";
import { Brand, Effect } from "effect";
import type { Reservation, ReservationRequest } from "./requestTypes";

/**
 * Type that certifies that a callback with no parameters is idempotent, meaning that multiple calls to this callback will return the same value and have the same effect as a single call.
 */
export type IdempotentCallable<T> = Brand.Brand<"IdempotentCallable"> & (() => T);

/**
 * Constructor for an IdempotentCallable. Makes a function idempotent by caching its result and ensuring that subsequent calls return the cached result without calling the original function again.
 */
const IdempotentCallable = <T>(fn: () => T): IdempotentCallable<T> => {
	let called = false;
	let result: T;
	const callable = () => {
		if (!called) {
			result = fn();
			called = true;
		}
		return result;
	};
	return Brand.nominal<IdempotentCallable<T>>()(callable);
};

/**
 * A provisional value is a data representation of some resource that exists strictly on the frontend. It is used as a placeholder for a corresponding server resource that may or may not exist yet, and can be used to make requests to the backend to create or modify the corresponding server resource.
 */
export type Prov<T> = T & Brand.Brand<"Prov">;

/**
 * Constructor for a Prov. Brands a value as a Prov. Mostly used for type safety and clarity.
 */
export function Prov<T>(value: Brand.Brand.Unbranded<Prov<T>>): Prov<T> {
	return Brand.nominal<Prov<T>>()(value);
}

/**
 * Most reservation requests can be specified at queue time using only a single array of provisional ids. This is a convenience function that returns a proper request event using some provided provisional ids. It is not meant to cover all use cases, and more complex reservation requests can be constructed manually using the {@link ReservationRequest} type.
 */
export function makeReservationRequest(
	idRepo: IDRepository,
	reserveList: Reservation[],
	skip?: () => boolean,
): ReservationRequest {
	const wait = () =>
		reserveList.some(
			({ kind, id, desiredState }) =>
				!Effect.runSyncExit(idRepo.isReserveable(kind, id, desiredState)),
		);
	return {
		reserveList: IdempotentCallable(() => reserveList),
		skip: skip ?? (() => false),
		wait,
	};
}
