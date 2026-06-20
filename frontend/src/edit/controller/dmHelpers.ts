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
	CProvId,
	LGProvId,
	ProvChapter,
	ProvId,
	ProvLabel,
	ProvLabelData,
	ProvLabelGroup,
} from "./types/idTypes";
import type { Slot, SlotIndex } from "./types/helperTypes";

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

interface SlotIndexInternals<IDT extends ProvId, Meta, Data, IndexErrorT> extends SlotIndex<
	IDT,
	Meta,
	Data,
	IndexErrorT
> {
	index: Map<IDT, Slot<Meta, Data>>;
}

/**
 * Efficient indexed set for chapter slots, which are frequently accessed by both chapter ID and chapter number, and require atomic updates to metadata and data.
 * Constraints:
 * - Chapter Number is unique and immutable for each chapter.
 * - Chapter ID is unique and immutable for each chapter.
 */
export interface ChapterIndex extends SlotIndex<
	CProvId,
	{ chapter: ProvChapter },
	{ chapterData: ChapterDataManager },
	DuplicateChapterNumException
> {
	/**
	 * Get chapter slot by chapter number.
	 */
	getByChapterNum: (chapterNum: number) => Effect.Effect<CProvId, NotFoundException>;
}

export interface LabelGroupIndex extends SlotIndex<
	LGProvId,
	{ labelGroup: ProvLabelGroup; role: LabelRole },
	never,
	never
> {}

export interface LabelDataIndex extends SlotIndex<
	LGProvId,
	{ labelData: ProvLabelData },
	{ labels: readonly ProvLabel[] },
	never
> {}

export const buildIndexInternals = <IDT extends ProvId, Meta, Data, IndexErrorT>(
	items: [IDT, Meta][],
): Effect.Effect<SlotIndexInternals<IDT, Meta, Data, IndexErrorT>, FatalException> =>
	Effect.gen(function* () {
		const ids = new Set(items.map(([id]) => id));
		if (ids.size !== items.length) {
			return yield* Effect.fail(
				new FatalException({ orig: new Error("Duplicate ID found in initial data") }),
			);
		}
		const index: Map<IDT, Slot<Meta, Data>> = new Map(
			items.map(([id, meta]) => [id, { meta, inFlight: 0, status: "idle" }]),
		);
		return {
			index,
			get: (id: IDT) => {
				const item = index.get(id);
				if (!item) {
					return Effect.fail(new NotFoundException());
				}
				return Effect.succeed(item);
			},
			getIds: () => Effect.succeed(Array.from(index.keys())),
			setMeta: (id: IDT, meta: Meta) => {
				const item = index.get(id);
				if (!item) {
					return Effect.fail(new NotFoundException());
				}
				index.set(id, { ...item, meta });
				return Effect.succeed(void 0);
			},
			setData: (
				id: IDT,
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
			increment: (id: IDT) => {
				const item = index.get(id);
				if (!item) {
					return Effect.fail(new NotFoundException());
				}
				index.set(id, { ...item, inFlight: item.inFlight + 1 });
				return Effect.succeed(void 0);
			},
			decrement: (id: IDT) => {
				const item = index.get(id);
				if (!item) {
					return Effect.fail(new NotFoundException());
				}
				index.set(id, { ...item, inFlight: item.inFlight - 1 });
				return Effect.succeed(void 0);
			},
			new: (id: IDT, meta: Meta) => {
				if (index.has(id)) {
					return Effect.fail(new DuplicateIdException({ id }));
				}
				index.set(id, { meta, inFlight: 0, status: "idle" });
				return Effect.succeed(void 0);
			},
		};
	});

export const buildChapterIndex = (
	items: [CProvId, { chapter: ProvChapter }][],
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
			CProvId,
			{ chapter: ProvChapter },
			{ chapterData: ChapterDataManager },
			DuplicateChapterNumException
		>(items);
		const numIndex = new Map(items.map(([id, item]) => [item.chapter.chapterNum, id]));
		return {
			get: internals.get,
			/**
			 * Returns sorted list of all chapter ids based on chapterNum.
			 */
			getIds: () =>
				Effect.succeed(
					Array.from(numIndex.entries())
						.sort(([a], [b]) => a - b)
						.map(([, id]) => id),
				),
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
				if (
					numIndex.has(val.chapter.chapterNum) &&
					numIndex.get(val.chapter.chapterNum) !== id
				) {
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
	items: [LGProvId, { labelGroup: ProvLabelGroup; role: LabelRole }][],
): Effect.Effect<LabelGroupIndex, FatalException> =>
	buildIndexInternals<LGProvId, { labelGroup: ProvLabelGroup; role: LabelRole }, never, never>(
		items,
	);

export const buildLabelDataIndex = (): Effect.Effect<LabelDataIndex, FatalException> =>
	buildIndexInternals<
		LGProvId,
		{ labelData: ProvLabelData },
		{ labels: readonly ProvLabel[] },
		never
	>([]);
