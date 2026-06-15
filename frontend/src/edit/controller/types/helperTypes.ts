import type { IDRepository } from "./idTypes";
import { Brand } from "effect";
import type { Reservation, ReservationRequest } from "./requestTypes";

export type IdempotentCallable<T> = Brand.Brand<"IdempotentCallable"> & (() => T);

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

export type Prov<T> = T & Brand.Brand<"Prov">;

export function Prov<T>(value: Brand.Brand.Unbranded<Prov<T>>): Prov<T> {
	return Brand.nominal<Prov<T>>()(value);
}

export function makeReservationRequest(
	idRepo: IDRepository,
	reserveList: Reservation[],
	skip?: () => boolean,
): ReservationRequest {
	const wait = () =>
		reserveList.some(({ kind, id, desiredState }) => !idRepo.isReserveable(kind, id, desiredState));
	return {
		reserveList: IdempotentCallable(() => reserveList),
		skip: skip ?? (() => false),
		wait,
	};
}
