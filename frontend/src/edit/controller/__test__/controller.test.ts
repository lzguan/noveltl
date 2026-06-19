import { describe, expect, it, vi } from "vitest";
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
	it("builds successfully", () => {
		const controller = Effect.runSync(buildNovelController(makeNovelData()));
		expect(controller).toBeDefined();
		expect(controller.handleUserEvent).toBeTypeOf("function");
		expect(controller.subscribe).toBeTypeOf("function");
		expect(controller.start).toBeTypeOf("function");
		expect(controller.stop).toBeTypeOf("function");
	});

	it("ignores events when not running", () => {
		const controller = Effect.runSync(buildNovelController(makeNovelData()));
		const subscriber = vi.fn();
		controller.subscribe((_getters: NovelGetters, _event: TriggerEvent) => Effect.succeed(void 0));

		controller.handleUserEvent({
			eventType: "addLabelGroup",
			labelGroupName: "Test",
		});
	});

	it("raises error trigger event when chapter not loaded", () => {
		const controller = Effect.runSync(buildNovelController(makeNovelData()));
		const events: TriggerEvent[] = [];
		controller.subscribe((_getters: NovelGetters, event: TriggerEvent) => {
			events.push(event);
			return Effect.succeed(void 0);
		});
		controller.start();

		const fakeChapterId = CProvId("00000000-0000-0000-0000-ffffffffffff");
		controller.handleUserEvent({
			eventType: "textOp",
			op: { op: "insert", start: 0, text: "Hello" },
			chapterId: fakeChapterId,
		});

		const errorEvent = events.find(
			(e) => e.eventType === "errorOccured" && e.from === "dataManager",
		);
		expect(errorEvent).toBeDefined();
	});

	it("subscribe returns working unsubscribe function", () => {
		const controller = Effect.runSync(buildNovelController(makeNovelData()));
		const events: TriggerEvent[] = [];
		const unsubscribe = controller.subscribe(
			(_getters: NovelGetters, event: TriggerEvent) => {
				events.push(event);
				return Effect.succeed(void 0);
			},
		);
		controller.start();

		const fakeChapterId = CProvId("00000000-0000-0000-0000-ffffffffffff");
		controller.handleUserEvent({
			eventType: "textOp",
			op: { op: "insert", start: 0, text: "A" },
			chapterId: fakeChapterId,
		});
		expect(events.length).toBeGreaterThan(0);

		const countBefore = events.length;
		unsubscribe();

		controller.handleUserEvent({
			eventType: "textOp",
			op: { op: "insert", start: 0, text: "B" },
			chapterId: fakeChapterId,
		});
		expect(events.length).toBe(countBefore);
	});

	it("provides getters with novel data", () => {
		const controller = Effect.runSync(buildNovelController(makeNovelData()));

		expect(controller.getters.id()).toBeDefined();
		expect(controller.getters.chapters()).toHaveLength(1);
		expect(controller.getters.labelGroups()).toHaveLength(0);
	});

	it("processes addLabelGroup when running", () => {
		const controller = Effect.runSync(buildNovelController(makeNovelData()));
		const events: TriggerEvent[] = [];
		controller.subscribe((_getters: NovelGetters, event: TriggerEvent) => {
			events.push(event);
			return Effect.succeed(void 0);
		});
		controller.start();

		controller.handleUserEvent({
			eventType: "addLabelGroup",
			labelGroupName: "Characters",
		});

		const addEvent = events.find((e) => e.eventType === "labelGroupAdded");
		expect(addEvent).toBeDefined();
		expect(controller.getters.labelGroups()).toHaveLength(1);
	});
});
