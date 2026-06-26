import { describe, expect, it } from "vitest";
import { Effect } from "effect";
import { buildRequestQueueDispatcher } from "../dmHelpers";
import { isAllReserveable } from "../types/helperTypes";
import { CProvId, LGProvId, LProvId, type IDRepository } from "../types/idTypes";
import { NotFoundException } from "../types/errors";
import type { ReserveList } from "../types/requestTypes";

interface TestEvent {
	active: boolean;
	name: string;
}

describe("buildRequestQueueDispatcher", () => {
	it("accumulates multiple passive events until an active event flushes them", () => {
		const { decorate } = buildRequestQueueDispatcher<TestEvent>();

		const producePassive = decorate(() => Effect.succeed([{ active: false, name: "p" }]));
		const produceActive = decorate(() => Effect.succeed([{ active: true, name: "a" }]));

		Effect.runSync(producePassive());
		Effect.runSync(producePassive());
		Effect.runSync(producePassive());

		const result = Effect.runSync(produceActive());
		expect(result).toEqual([
			{ active: false, name: "p" },
			{ active: false, name: "p" },
			{ active: false, name: "p" },
			{ active: true, name: "a" },
		]);
	});

	it("flush() drains the passive queue", () => {
		const { decorate, flush } = buildRequestQueueDispatcher<TestEvent>();

		const producePassive = decorate(() =>
			Effect.succeed([
				{ active: false, name: "p1" },
				{ active: false, name: "p2" },
			]),
		);

		Effect.runSync(producePassive());

		const flushed = Effect.runSync(flush());
		expect(flushed).toEqual([
			{ active: false, name: "p1" },
			{ active: false, name: "p2" },
		]);

		const flushedAgain = Effect.runSync(flush());
		expect(flushedAgain).toEqual([]);
	});

	it("handles mixed active and passive events in a single result", () => {
		const { decorate } = buildRequestQueueDispatcher<TestEvent>();

		const produceMixed = decorate(() =>
			Effect.succeed([
				{ active: false, name: "p1" },
				{ active: true, name: "a1" },
				{ active: false, name: "p2" },
				{ active: true, name: "a2" },
			]),
		);

		const result = Effect.runSync(produceMixed());
		expect(result).toEqual([
			{ active: false, name: "p1" },
			{ active: true, name: "a1" },
			{ active: false, name: "p2" },
			{ active: true, name: "a2" },
		]);
	});
});

describe("isAllReserveable", () => {
	function makeMockIdRepo(reserveableMap: Map<string, boolean>): IDRepository {
		return {
			isReserveable: (_kind: string, id: unknown, _desiredState: string) =>
				Effect.gen(function* () {
					const key = String(id);
					if (!reserveableMap.has(key)) {
						return yield* Effect.fail(new NotFoundException());
					}
					return reserveableMap.get(key)!;
				}),
		} as unknown as IDRepository;
	}

	it("returns true when all entries are reserveable", () => {
		const chapterId = CProvId("ch-1");
		const labelGroupId = LGProvId("lg-1");

		const idRepo = makeMockIdRepo(
			new Map([
				[String(chapterId), true],
				[String(labelGroupId), true],
			]),
		);

		const list: ReserveList = {
			chapter: [{ id: chapterId, kind: "chapter", desiredState: "locked" }],
			chapterContent: [],
			label: [],
			labelData: [],
			labelGroup: [{ id: labelGroupId, kind: "labelGroup", desiredState: "locked" }],
		};

		const result = Effect.runSync(isAllReserveable(idRepo, list));
		expect(result).toBe(true);
	});

	it("returns false when any entry is not reserveable", () => {
		const chapterId = CProvId("ch-1");
		const labelGroupId = LGProvId("lg-1");

		const idRepo = makeMockIdRepo(
			new Map([
				[String(chapterId), true],
				[String(labelGroupId), false],
			]),
		);

		const list: ReserveList = {
			chapter: [{ id: chapterId, kind: "chapter", desiredState: "locked" }],
			chapterContent: [],
			label: [],
			labelData: [],
			labelGroup: [{ id: labelGroupId, kind: "labelGroup", desiredState: "locked" }],
		};

		const result = Effect.runSync(isAllReserveable(idRepo, list));
		expect(result).toBe(false);
	});

	it("returns true for empty reserve list", () => {
		const idRepo = makeMockIdRepo(new Map());

		const list: ReserveList = {
			chapter: [],
			chapterContent: [],
			label: [],
			labelData: [],
			labelGroup: [],
		};

		const result = Effect.runSync(isAllReserveable(idRepo, list));
		expect(result).toBe(true);
	});

	it("short-circuits on first non-reserveable entry", () => {
		let callCount = 0;
		const labelId1 = LProvId("l-1");
		const labelId2 = LProvId("l-2");
		const labelId3 = LProvId("l-3");

		const idRepo = {
			isReserveable: (_kind: string, id: unknown, _desiredState: string) => {
				callCount++;
				const key = String(id);
				if (key === String(labelId2)) {
					return Effect.succeed(false);
				}
				return Effect.succeed(true);
			},
		} as unknown as IDRepository;

		const list: ReserveList = {
			chapter: [],
			chapterContent: [],
			label: [
				{ id: labelId1, kind: "label", desiredState: "detaching" },
				{ id: labelId2, kind: "label", desiredState: "detaching" },
				{ id: labelId3, kind: "label", desiredState: "detaching" },
			],
			labelData: [],
			labelGroup: [],
		};

		const result = Effect.runSync(isAllReserveable(idRepo, list));
		expect(result).toBe(false);
		expect(callCount).toBe(2);
	});
});
