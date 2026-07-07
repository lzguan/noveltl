import {
	AProvId,
	kinds,
	ProvId,
	type IDRepository,
	type Kind,
	type ProvAutoLabel,
	type ProvAutoLabelMetaWithCid,
	type ProvAutoLabelRun,
	type ProvChapter,
	type ProvLabel,
	type ProvLabelData,
	type ProvLabelGroup,
} from "./idTypes";
import { Brand, Effect } from "effect";
import {
	NotReserveableException,
	type DuplicateProvIdException,
	type NotFoundException,
} from "./errors";
import type { AnyReservation, ReservationRequest, ReserveList } from "./requestTypes";
import type { LabelRole } from "@/api/models";
import type { ChapterDataManager } from "./dataTypes";
import type { ChapterGetters } from "./controllerTypes";

/**
 * Type that certifies that a callback with no parameters is idempotent, meaning that multiple calls to this callback will return the same value and have the same effect as a single call.
 */
export type IdempotentCallable<T> = Brand.Brand<"IdempotentCallable"> & (() => T);

/**
 * Constructor for an IdempotentCallable. Makes a function idempotent by caching its result and ensuring that subsequent calls return the cached result without calling the original function again.
 */
export const IdempotentCallable = <T>(fn: () => T): IdempotentCallable<T> => {
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

export const forEachKind = <E, V, I extends Iterable<V>, K extends Kind, T extends { [U in K]: I }>(
	hasKinds: T,
	f: (value: V) => Effect.Effect<void, E>,
	kindsList: readonly K[],
): Effect.Effect<void, E> =>
	Effect.gen(function* () {
		for (const kind of kindsList) {
			yield* Effect.forEach(hasKinds[kind], (value) => f(value));
		}
	});

/**
 * Checks whether all entries in a ReserveList are reserveable for their desired states.
 * Short-circuits on first false.
 *
 * @param idRepo - ID repository to check reservation state against.
 * @param list - Reserve list to validate.
 * @returns true if all reserveable, false otherwise.
 */
export const isAllReserveable = (
	idRepo: IDRepository,
	list: ReserveList,
): Effect.Effect<boolean, NotFoundException> =>
	Effect.gen(function* () {
		let out = true;
		yield* forEachKind(
			list,
			(reservation: AnyReservation<Kind>) =>
				Effect.gen(function* () {
					const reserveable = yield* idRepo.isReserveable(reservation);
					if (!reserveable) return yield* Effect.fail(new NotReserveableException());
					return true;
				}).pipe(
					Effect.catch("_tag", {
						failure: "NotReserveableException",
						onFailure: () => {
							out = false;
							return Effect.succeed(void 0);
						},
					}),
				),
			kinds,
		);
		return out;
	});

/**
 * Convenience constructor for simple reservation requests where wait() = "are all IDs reserveable?".
 * For complex cases (custom wait logic, dynamic reserve lists), construct ReservationRequest manually.
 *
 * @param idRepo - ID repository for reservation checks.
 * @param reserveList - Static list of reservations. Wrapped in IdempotentCallable internally.
 * @param skip - Optional predicate; if true, the request is skipped entirely. Defaults to () => false.
 */
export function makeReservationRequest(
	idRepo: IDRepository,
	reserveList: ReserveList,
	skip?: () => boolean,
): ReservationRequest {
	return {
		reserveList: IdempotentCallable(() => reserveList),
		skip: skip ?? (() => false),
		wait: () => isAllReserveable(idRepo, reserveList).pipe(Effect.map((ready) => !ready)),
	};
}

/**
 * A slot is an abstraction for a resource with both metadata and data on the backend. The metadata is a resource we try to keep up-to-date and consistent with the backend, while the data is a resource that is lazy loaded on demand and can be in one of several states.
 *
 * A slot has the following fields:
 * - `inFlight`: number of in-flight requests related to the metadata, used to keep track of whether the metadata is currently being modified. (Note: not used for locking.)
 * - `error`: error encountered during the last request that modified the metadata, if any.
 * - `Meta`: this is a type, whose fields we insert into the `Slot` type. This represents the metadata of the resource, which we try to keep up-to-date and consistent with the backend.
 * - `Data`: this is a type, whose fields we insert into the `Slot` type. This represents the data of the resource, which is lazy loaded on demand and possibly undefined if not loaded.
 * - `status`: this field represents the loading status of the data. It can be "idle" (not loaded), "loading" (currently loading), "error" (encountered an error during loading), or "ready" (successfully loaded and available).
 *
 * We maintain the following constraints on the readiness of the data in relation to the status:
 * - If `status` is "ready", then the data fields must be defined.
 * - If `status` is "idle", "loading", or "error", then the data fields must not be defined.
 *
 * The metadata and the data are updated through separate mechanisms. The metadata is updated through direct state updates in response to user actions and server responses, while the data is updated through explicit load operations that fetch the data from the server and update the slot accordingly.
 *
 * Note: this is the intended use of the type, not an implementation. Implementations should try to adhere to these constraints.
 */
export type Slot<Meta, Data = never> = { inFlight: number; error?: Error; meta: Meta } & ([
	Data,
] extends [never]
	? {}
	: { status: "ready"; data: Data } | { status: "idle" | "loading" | "error" });

/**
 * Interface for an index that stores slots.
 */
export interface SlotIndex<IDT extends ProvId, Meta, Data, IndexErrorT> {
	/**
	 * Get slot by ID.
	 */
	get: (id: IDT) => Effect.Effect<Slot<Meta, Data>, NotFoundException>;
	/**
	 * Get all ids.
	 */
	getIds: () => Effect.Effect<IDT[]>;
	/**
	 * Set chapter slot metadata by ID. Does not allow changing chapterNum.
	 */
	setMeta: (id: IDT, val: Meta) => Effect.Effect<void, NotFoundException | IndexErrorT>;
	/**
	 * Set slot data by ID.
	 */
	setData: (
		id: IDT,
		val: { status: "idle" | "loading" | "error" } | { status: "ready"; data: Data },
	) => Effect.Effect<void, NotFoundException>;
	/**
	 * Delete slot by ID.
	 */
	delete: (id: IDT) => Effect.Effect<void, NotFoundException>;
	/**
	 * Increment the in-flight count for a slot by id.
	 */
	increment: (id: IDT) => Effect.Effect<void, NotFoundException>;
	/**
	 * Decrement the in-flight count for a slot by id.
	 */
	decrement: (id: IDT) => Effect.Effect<void, NotFoundException>;
	/**
	 * Create a new slot with given id and metadata.
	 */
	new: (id: IDT, meta: Meta) => Effect.Effect<void, DuplicateProvIdException | IndexErrorT>;
}

// -----------------------------------------
// --------- Concrete Slot Types -----------
// -----------------------------------------
export type LabelDataSlot = Slot<{ labelData: ProvLabelData }, { labels: readonly ProvLabel[] }>;

export type LabelGroupSlot = Slot<{ labelGroup: ProvLabelGroup; role: LabelRole }>;

export type ChapterSlot = Slot<{ chapter: ProvChapter }, { chapterData: ChapterDataManager }>;

export type ChapterGetterSlot = Slot<{ chapter: ProvChapter }, { chapterGetters: ChapterGetters }>;

export type AutoLabelSlot = Slot<
	{ autoLabel: ProvAutoLabelMetaWithCid },
	{ autoLabelData: ProvAutoLabel["autoLabelData"] }
>;

export type AutoLabelIndex = SlotIndex<
	AProvId,
	{ autoLabel: ProvAutoLabelMetaWithCid },
	{ autoLabelData: ProvAutoLabel["autoLabelData"] },
	never
>;

export type AutoLabelRunSlot = Slot<{ run: ProvAutoLabelRun }, { index: AutoLabelIndex }>;

export type AutoLabelGetterSlot = Slot<
	{ autoLabel: ProvAutoLabelMetaWithCid },
	{ autoLabelData: ProvAutoLabel["autoLabelData"] }
>;

export type AutoLabelRunGetterSlot = Slot<
	{ run: ProvAutoLabelRun },
	{ autolabels: readonly AutoLabelGetterSlot[] }
>;
