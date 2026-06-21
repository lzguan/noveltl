import { describe, expect, it } from "vitest";
import { Effect } from "effect";
import { buildNovelController } from "../controller";
import type { NovelData } from "../dataManager";
import { CProvId } from "../types/idTypes";
import type { NovelGetters, TriggerEvent } from "../types/controllerTypes";

const NOVEL_UUID = "00000000-0000-0000-0000-00000000000a";
const CHAPTER_UUID = "00000000-0000-0000-0000-000000000001";

function makeNovelData(): NovelData {
	return {
		novel: {
			novelId: NOVEL_UUID,
			novelTitle: "Test Novel",
			novelDescription: null,
			novelAuthor: "Author",
			novelVisibility: 0,
			novelType: "original",
			languageCode: "en",
			sourceWorkId: "00000000-0000-0000-0000-00000000000b",
		},
		chapters: [
			{
				chapterId: CHAPTER_UUID,
				chapterNum: 1,
				chapterTitle: "Chapter 1",
				chapterIsPublic: false,
				novelId: NOVEL_UUID,
			},
		],
		labelGroups: [],
		novelRole: "owner",
	};
}

describe("buildNovelController", () => {
	it("ignores events when not running", () => {
		const controller = Effect.runSync(buildNovelController(makeNovelData()));
		const events: TriggerEvent[] = [];
		controller.subscribe((_getters: NovelGetters, event: TriggerEvent) => {
			events.push(event);
			return Effect.succeed(void 0);
		});

		Effect.runSync(
			controller.handleUserEvent({
				eventType: "addLabelGroup",
				labelGroupName: "Test",
			}),
		);

		expect(events).toHaveLength(0);
		expect(Effect.runSync(controller.getters.labelGroupIds())).toHaveLength(0);
	});

	it("raises error trigger event when chapter not loaded", async () => {
		const controller = Effect.runSync(buildNovelController(makeNovelData()));
		const events: TriggerEvent[] = [];
		controller.subscribe((_getters: NovelGetters, event: TriggerEvent) => {
			events.push(event);
			return Effect.succeed(void 0);
		});
		controller.start(); // sets running = true synchronously

		const fakeChapterId = CProvId("00000000-0000-0000-0000-ffffffffffff");
		await Effect.runPromise(
			controller.handleUserEvent({
				eventType: "textOp",
				op: { op: "insert", start: 0, text: "Hello" },
				chapterId: fakeChapterId,
			}),
		);

		const errorEvent = events.find(
			(e) => e.eventType === "errorOccured" && e.from === "dataManager",
		);
		expect(errorEvent).toBeDefined();
	});

	it("subscribe returns working unsubscribe function", async () => {
		const controller = Effect.runSync(buildNovelController(makeNovelData()));
		const events: TriggerEvent[] = [];
		const unsubscribe = controller.subscribe(
			(_getters: NovelGetters, event: TriggerEvent) => {
				events.push(event);
				return Effect.succeed(void 0);
			},
		);
		controller.start(); // sets running = true synchronously

		const fakeChapterId = CProvId("00000000-0000-0000-0000-ffffffffffff");
		await Effect.runPromise(
			controller.handleUserEvent({
				eventType: "textOp",
				op: { op: "insert", start: 0, text: "A" },
				chapterId: fakeChapterId,
			}),
		);
		expect(events.length).toBeGreaterThan(0);

		const countBefore = events.length;
		unsubscribe();

		await Effect.runPromise(
			controller.handleUserEvent({
				eventType: "textOp",
				op: { op: "insert", start: 0, text: "B" },
				chapterId: fakeChapterId,
			}),
		);
		expect(events.length).toBe(countBefore);
	});

	it("provides getters with novel data", () => {
		const controller = Effect.runSync(buildNovelController(makeNovelData()));

		expect(Effect.runSync(controller.getters.novel()).novelId).toBe(NOVEL_UUID);
		const chapters = Effect.runSync(controller.getters.chapterIds());
		expect(chapters).toHaveLength(1);
		expect(Effect.runSync(controller.getters.labelGroupIds())).toHaveLength(0);
	});

	it("processes addLabelGroup when running", async () => {
		const controller = Effect.runSync(buildNovelController(makeNovelData()));
		const events: TriggerEvent[] = [];
		controller.subscribe((_getters: NovelGetters, event: TriggerEvent) => {
			events.push(event);
			return Effect.succeed(void 0);
		});
		controller.start(); // sets running = true synchronously

		await Effect.runPromise(
			controller.handleUserEvent({
				eventType: "addLabelGroup",
				labelGroupName: "Characters",
			}),
		);

		const addEvent = events.find((e) => e.eventType === "labelGroupAdded");
		expect(addEvent).toBeDefined();
		expect(Effect.runSync(controller.getters.labelGroupIds())).toHaveLength(1);
	});
});
