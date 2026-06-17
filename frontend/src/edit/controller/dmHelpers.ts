import type { ChapterDataManager } from "./types/dataTypes";
import type { LabelRole } from "@/api/models";
import { Effect } from "effect";
import {
	FatalException,
	NotFoundException,
	DuplicateChapterNumException,
	DuplicateIdException,
} from "./types/errors";
import type {
	ProvChapter,
	ProvId,
	ProvLabel,
	ProvLabelData,
	ProvLabelGroup,
} from "./types/idTypes";

interface HasActiveAttribute {
	active: boolean;
}

type Dequeuer<T extends HasActiveAttribute, Params extends unknown[], E> = (
	...params: [...Params]
) => Effect.Effect<T[], E>;

type RequestQueueDispatcher<T extends HasActiveAttribute> = {
	decorate: <Params extends unknown[], E>(f: Dequeuer<T, Params, E>) => Dequeuer<T, Params, E>;
	flush: () => Effect.Effect<T[]>;
};

export function buildRequestQueueDispatcher<
	T extends HasActiveAttribute,
>(): RequestQueueDispatcher<T> {
	const queue: T[] = [];
	const decorate =
		<Params extends unknown[], E>(f: Dequeuer<T, Params, E>) =>
		(...params: [...Params]) =>
			Effect.gen(function* () {
				const result = yield* f(...params);
				const out: T[] = [];
				for (const item of result) {
					if (item.active) {
						out.push(...queue);
						queue.length = 0;
						out.push(item);
					} else {
						queue.push(item);
					}
				}
				return out;
			});

	const flush = () => {
		const out = [...queue];
		queue.length = 0;
		return Effect.succeed(out);
	};

	return {
		decorate,
		flush,
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
type Slot<Meta, Data = never> = { inFlight: number; error?: Error; meta: Meta } & ([Data] extends [
	never,
]
	? {}
	: { status: "ready"; data: Data } | { status: "idle" | "loading" | "error" });

/**
 * Interface for an index that stores slots.
 */
interface SlotIndex<Meta, Data, IndexErrorT> {
	/**
	 * Get slot by ID.
	 */
	get: (id: ProvId) => Effect.Effect<Slot<Meta, Data>, NotFoundException>;
	/**
	 * Set chapter slot metadata by ID. Does not allow changing chapterNum.
	 */
	setMeta: (id: ProvId, val: Meta) => Effect.Effect<void, NotFoundException | IndexErrorT>;
	/**
	 * Set slot data by ID.
	 */
	setData: (
		id: ProvId,
		val: { status: "idle" | "loading" | "error" } | { status: "ready"; data: Data },
	) => Effect.Effect<void, NotFoundException>;
	/**
	 * Increment the in-flight count for a slot by id.
	 */
	increment: (id: ProvId) => Effect.Effect<void, NotFoundException>;
	/**
	 * Decrement the in-flight count for a slot by id.
	 */
	decrement: (id: ProvId) => Effect.Effect<void, NotFoundException>;
	/**
	 * Create a new slot with given id and metadata.
	 */
	new: (id: ProvId, meta: Meta) => Effect.Effect<void, DuplicateIdException | IndexErrorT>;
}

interface SlotIndexInternals<Meta, Data, IndexErrorT> extends SlotIndex<Meta, Data, IndexErrorT> {
	index: Map<ProvId, Slot<Meta, Data>>;
}

// -----------------------------------------
// --------- Concrete Slot Types -----------
// -----------------------------------------
export type LabelDataSlot = Slot<{ labelData: ProvLabelData }, { labels: readonly ProvLabel[] }>;

export type LabelGroupSlot = Slot<{ labelGroup: ProvLabelGroup; role: LabelRole }>;

export type ChapterSlot = Slot<{ chapter: ProvChapter }, { chapterData: ChapterDataManager }>;

/**
 * Efficient indexed set for chapter slots, which are frequently accessed by both chapter ID and chapter number, and require atomic updates to metadata and data.
 * Constraints:
 * - Chapter Number is unique and immutable for each chapter.
 * - Chapter ID is unique and immutable for each chapter.
 */
export interface ChapterIndex extends SlotIndex<
	{ chapter: ProvChapter },
	{ chapterData: ChapterDataManager },
	DuplicateChapterNumException
> {
	/**
	 * Get chapter slot by chapter number.
	 */
	getByChapterNum: (chapterNum: number) => Effect.Effect<ProvId, NotFoundException>;
}

export interface LabelGroupIndex extends SlotIndex<
	{ labelGroup: ProvLabelGroup; role: LabelRole },
	never,
	never
> {}

export interface LabelDataIndex extends SlotIndex<
	{ labelData: ProvLabelData },
	{ labels: readonly ProvLabel[] },
	never
> {}

export const buildIndexInternals = <Meta, Data, IndexErrorT>(
	items: [ProvId, Meta][],
): Effect.Effect<SlotIndexInternals<Meta, Data, IndexErrorT>, FatalException> =>
	Effect.gen(function* () {
		const ids = new Set(items.map(([id]) => id));
		if (ids.size !== items.length) {
			return yield* Effect.fail(
				new FatalException({ orig: new Error("Duplicate ID found in initial data") }),
			);
		}
		const index: Map<ProvId, Slot<Meta, Data>> = new Map(
			items.map(([id, meta]) => [id, { meta, inFlight: 0, status: "idle" }]),
		);
		return {
			index,
			get: (id: ProvId) => {
				const item = index.get(id);
				if (!item) {
					return Effect.fail(new NotFoundException());
				}
				return Effect.succeed(item);
			},
			setMeta: (id: ProvId, meta: Meta) => {
				const item = index.get(id);
				if (!item) {
					return Effect.fail(new NotFoundException());
				}
				index.set(id, { ...item, meta });
				return Effect.succeed(void 0);
			},
			setData: (
				id: ProvId,
				data: { status: "idle" | "loading" | "error" } | { status: "ready"; data: Data },
			) => {
				const item = index.get(id);
				if (!item) {
					return Effect.fail(new NotFoundException());
				}
				index.set(id, {
					...item,
					status: data.status,
					data: "data" in data ? data.data : undefined,
				});
				return Effect.succeed(void 0);
			},
			increment: (id: ProvId) => {
				const item = index.get(id);
				if (!item) {
					return Effect.fail(new NotFoundException());
				}
				index.set(id, { ...item, inFlight: item.inFlight + 1 });
				return Effect.succeed(void 0);
			},
			decrement: (id: ProvId) => {
				const item = index.get(id);
				if (!item) {
					return Effect.fail(new NotFoundException());
				}
				index.set(id, { ...item, inFlight: item.inFlight - 1 });
				return Effect.succeed(void 0);
			},
			new: (id: ProvId, meta: Meta) => {
				if (index.has(id)) {
					return Effect.fail(new DuplicateIdException({ id }));
				}
				index.set(id, { meta, inFlight: 0, status: "idle" });
				return Effect.succeed(void 0);
			},
		};
	});

export const buildChapterIndex = (
	items: [ProvId, { chapter: ProvChapter }][],
): Effect.Effect<ChapterIndex, FatalException> =>
	Effect.gen(function* () {
		const nums = new Set(items.map(([, item]) => item.chapter.chapterNum));
		if (nums.size !== items.length) {
			return yield* Effect.fail(
				new FatalException({
					orig: new Error("Duplicate chapterNum found in initial chapter data"),
				}),
			);
		}
		const internals = yield* buildIndexInternals<
			{ chapter: ProvChapter },
			{ chapterData: ChapterDataManager },
			DuplicateChapterNumException
		>(items);
		const numIndex = new Map(items.map(([id, item]) => [item.chapter.chapterNum, id]));
		return {
			get: internals.get,
			getByChapterNum: (chapterNum: number) => {
				const id = numIndex.get(chapterNum);
				if (!id) {
					return Effect.fail(new NotFoundException());
				}
				return Effect.succeed(id);
			},
			setMeta: (id, val) => {
				const item = internals.index.get(id);
				if (!item) {
					return Effect.fail(new NotFoundException());
				}
				if (numIndex.has(val.chapter.chapterNum) && numIndex.get(val.chapter.chapterNum) !== id) {
					return Effect.fail(new DuplicateChapterNumException());
				} else if (val.chapter.chapterNum !== item.meta.chapter.chapterNum) {
					numIndex.delete(item.meta.chapter.chapterNum);
					numIndex.set(val.chapter.chapterNum, id);
				}
				return internals.setMeta(id, val);
			},
			setData: internals.setData,
			increment: internals.increment,
			decrement: internals.decrement,
			new: (id, meta) => {
				if (numIndex.has(meta.chapter.chapterNum)) {
					return Effect.fail(new DuplicateChapterNumException());
				}
				numIndex.set(meta.chapter.chapterNum, id);
				return internals.new(id, meta);
			},
		};
	});

export const buildLabelGroupIndex = (
	items: [ProvId, { labelGroup: ProvLabelGroup; role: LabelRole }][],
): Effect.Effect<LabelGroupIndex, FatalException> =>
	buildIndexInternals<{ labelGroup: ProvLabelGroup; role: LabelRole }, never, never>(items);

export const buildLabelDataIndex = (): Effect.Effect<LabelDataIndex, FatalException> =>
	buildIndexInternals<{ labelData: ProvLabelData }, { labels: readonly ProvLabel[] }, never>([]);
