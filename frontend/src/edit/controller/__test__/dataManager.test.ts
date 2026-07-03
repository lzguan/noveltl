import { describe, expect, it, vi } from "vitest";
import { Effect } from "effect";
import { buildChapterDataManager } from "../chapterDataManager";
import { buildIdRepository } from "../idRepository";
import { CServId, LGServId } from "../types/idTypes";
import type { TriggerEvent } from "../types/controllerTypes";
import { Prov } from "../types/helperTypes";
import { buildLabelGroupIndex } from "../dmHelpers";
import { Visibility, type Novel } from "@/api/models";
import type { Role } from "@/api/models/role";
import { RequestKey } from "../types/requestTypes";
import { updateChapterContentChaptersChapterIdContentPatch } from "@/api/endpoints/default/default";

vi.mock("@/api/endpoints/default/default", async (importOriginal) => {
	const actual = await importOriginal<typeof import("@/api/endpoints/default/default")>();
	return {
		...actual,
		updateChapterContentChaptersChapterIdContentPatch: vi.fn(),
	};
});

const UUID1 = "00000000-0000-0000-0000-000000000001";
const UUID2 = "00000000-0000-0000-0000-000000000002";
const UUID3 = "00000000-0000-0000-0000-000000000003";
const UUID4 = "00000000-0000-0000-0000-000000000004";
const UUID5 = "00000000-0000-0000-0000-000000000005";
const UUID6 = "00000000-0000-0000-0000-000000000006";
const NOVEL_ID = "00000000-0000-0000-0000-00000000000a";
const SOURCE_WORK_ID = "00000000-0000-0000-0000-00000000000b";

const mockNovel: Novel = {
	novelId: NOVEL_ID,
	novelTitle: "Test Novel",
	novelType: "original",
	novelVisibility: Visibility.NUMBER_0,
	languageCode: "en",
	sourceWorkId: SOURCE_WORK_ID,
};
const mockRole: Role = "owner";

function buildTestChapterDM() {
	return Effect.gen(function* () {
		const idRepo = buildIdRepository();
		const triggerEvents: TriggerEvent[] = [];
		const raiseTriggerEvent = (event: TriggerEvent) =>
			Effect.sync(() => {
				triggerEvents.push(event);
			});

		const chapterId = Effect.runSync(idRepo.newIdAndBindId("chapter", CServId(UUID1)));
		const labelGroupProvId = Effect.runSync(
			idRepo.newIdAndBindId("labelGroup", LGServId(UUID3)),
		);

		const labelGroupsIndex = yield* buildLabelGroupIndex([
			[
				labelGroupProvId,
				{
					labelGroup: Prov({
						labelGroupId: labelGroupProvId,
						labelGroupName: "Characters",
						novelId: NOVEL_ID,
					}),
					role: "owner",
				},
			],
		]);

		const editChapterData = {
			chapterContent: {
				chapterContentId: UUID2,
				chapterContentText: "Alice met Bob at the park.",
				chapterContentVersion: 1,
			},
			eagerLabelData: [
				{
					labelGroup: {
						labelGroupId: UUID3,
						labelGroupName: "Characters",
						novelId: NOVEL_ID,
					},
					labelData: { labelDataId: UUID4, labelGroupId: UUID3, chapterContentId: UUID2 },
					labels: [
						{
							labelId: UUID5,
							labelDataId: UUID4,
							labelStart: 0,
							labelEnd: 5,
							labelWord: "Alice",
							labelEntityGroup: "character",
							labelScore: 1,
							labelDirty: false,
						},
						{
							labelId: UUID6,
							labelDataId: UUID4,
							labelStart: 10,
							labelEnd: 13,
							labelWord: "Bob",
							labelEntityGroup: "character",
							labelScore: 1,
							labelDirty: false,
						},
					],
				},
			],
			lazyLabelData: [],
			noLabelData: [],
		};

		const chapterDM = yield* buildChapterDataManager(
			editChapterData,
			chapterId,
			raiseTriggerEvent,
			idRepo,
			{
				labelGroupIds: () => labelGroupsIndex.getIds(),
				labelGroup: (lgId) => labelGroupsIndex.get(lgId),
				novel: () => Effect.succeed(mockNovel),
				role: () => Effect.succeed(mockRole),
			},
		);

		return { chapterDM, triggerEvents, labelGroupId: labelGroupProvId, chapterId };
	});
}

describe("buildChapterDataManager", () => {
	describe("addLabel", () => {
		it("adds a label and raises a trigger event", () => {
			const { chapterDM, triggerEvents, labelGroupId } = Effect.runSync(buildTestChapterDM());

			const events = Effect.runSync(
				chapterDM.addLabel(labelGroupId, 6, 9, "met", "verb", 0.9, true),
			);

			expect(events).toEqual([]);
			expect(triggerEvents).toHaveLength(1);
			expect(triggerEvents[0]).toMatchObject({
				eventType: "labelChanged",
				op: { op: "add", startPos: 6, endPos: 9, word: "met" },
			});
		});

		it("rejects overlapping labels", () => {
			const { chapterDM, labelGroupId } = Effect.runSync(buildTestChapterDM());

			const result = Effect.runSync(
				chapterDM.addLabel(labelGroupId, 3, 8, "ce me", "overlap").pipe(Effect.either),
			);

			expect(result._tag).toBe("Left");
		});

		it("rejects out-of-bounds positions", () => {
			const { chapterDM, labelGroupId } = Effect.runSync(buildTestChapterDM());

			const result = Effect.runSync(
				chapterDM.addLabel(labelGroupId, -1, 5, "Alice").pipe(Effect.either),
			);

			expect(result._tag).toBe("Left");
		});

		it("rejects word mismatch with text", () => {
			const { chapterDM, labelGroupId } = Effect.runSync(buildTestChapterDM());

			const result = Effect.runSync(
				chapterDM.addLabel(labelGroupId, 6, 9, "xyz").pipe(Effect.either),
			);

			expect(result._tag).toBe("Left");
		});
	});

	describe("deleteLabel", () => {
		it("deletes an existing label", () => {
			const { chapterDM, triggerEvents, labelGroupId } = Effect.runSync(buildTestChapterDM());

			const events = Effect.runSync(chapterDM.deleteLabel(labelGroupId, 0, 5));

			expect(events).toEqual([]);
			expect(triggerEvents).toHaveLength(1);
			expect(triggerEvents[0]).toMatchObject({
				eventType: "labelChanged",
				op: { op: "delete", startPos: 0, endPos: 5, word: "Alice" },
			});
		});

		it("rejects deleting nonexistent label", () => {
			const { chapterDM, labelGroupId } = Effect.runSync(buildTestChapterDM());

			const result = Effect.runSync(
				chapterDM.deleteLabel(labelGroupId, 7, 9).pipe(Effect.either),
			);

			expect(result._tag).toBe("Left");
		});
	});

	describe("auto-flush on tag mismatch", () => {
		it("flushes label ops when switching to text ops", () => {
			const { chapterDM, labelGroupId } = Effect.runSync(buildTestChapterDM());

			Effect.runSync(chapterDM.addLabel(labelGroupId, 6, 9, "met"));

			const events = Effect.runSync(chapterDM.insertTextAt(26, "!"));

			expect(events.length).toBeGreaterThan(0);
			expect(events[0]).toMatchObject({ variant: "labelOp", active: true });
		});

		it("flushes text ops when switching to label ops", () => {
			const { chapterDM, labelGroupId } = Effect.runSync(buildTestChapterDM());

			Effect.runSync(chapterDM.insertTextAt(26, "!"));

			const events = Effect.runSync(chapterDM.addLabel(labelGroupId, 6, 9, "met"));

			expect(events.length).toBeGreaterThan(0);
			expect(events[0]).toMatchObject({ variant: "textOp", active: true });
		});

		it("does not flush when same tag", () => {
			const { chapterDM, labelGroupId } = Effect.runSync(buildTestChapterDM());

			Effect.runSync(chapterDM.addLabel(labelGroupId, 6, 9, "met"));
			const events = Effect.runSync(chapterDM.deleteLabel(labelGroupId, 0, 5));

			expect(events).toEqual([]);
		});
	});

	describe("flush", () => {
		it("returns empty when nothing to flush", () => {
			const { chapterDM } = Effect.runSync(buildTestChapterDM());

			const events = Effect.runSync(chapterDM.flush());
			expect(events).toEqual([]);
		});

		it("creates cached text-op requests that pass request keys", async () => {
			const updateChapterContentMock = vi.mocked(
				updateChapterContentChaptersChapterIdContentPatch,
			);
			updateChapterContentMock.mockResolvedValue({
				status: 200,
				data: {
					chapterContentId: "00000000-0000-0000-0000-000000000007",
					chapterContentVersion: 2,
					labelDataIdMap: {
						[UUID4]: "00000000-0000-0000-0000-000000000008",
					},
				},
				headers: new Headers(),
			});
			const { chapterDM } = Effect.runSync(buildTestChapterDM());
			const requestKey = RequestKey("00000000-0000-0000-0000-000000000009");

			Effect.runSync(chapterDM.insertTextAt(26, "!"));
			const events = Effect.runSync(chapterDM.flush());

			expect(events).toHaveLength(1);
			expect(events[0]).toMatchObject({ variant: "textOp", cached: true });

			await Effect.runPromise(events[0].send(requestKey));

			expect(updateChapterContentMock).toHaveBeenCalledWith(
				UUID1,
				{
					chapterContentId: UUID2,
					textOps: [{ op: "insert", start: 26, text: "!" }],
				},
				{ requestKey },
			);
		});

		it("resets op queue after flush", () => {
			const { chapterDM, labelGroupId } = Effect.runSync(buildTestChapterDM());

			Effect.runSync(chapterDM.addLabel(labelGroupId, 6, 9, "met"));
			Effect.runSync(chapterDM.flush());
			const events = Effect.runSync(chapterDM.flush());

			expect(events).toEqual([]);
		});
	});

	describe("insertTextAt", () => {
		it("shifts labels after insertion point", () => {
			const { chapterDM, triggerEvents, labelGroupId } = Effect.runSync(buildTestChapterDM());

			Effect.runSync(chapterDM.insertTextAt(6, "bravely "));

			expect(triggerEvents[0]).toMatchObject({
				eventType: "textChanged",
				op: { op: "insert", start: 6, text: "bravely " },
			});

			Effect.runSync(chapterDM.flush());

			const deleteResult = Effect.runSync(
				chapterDM.deleteLabel(labelGroupId, 18, 21).pipe(Effect.either),
			);
			expect(deleteResult._tag).toBe("Right");
		});

		it("drops labels straddling insertion point", () => {
			const { chapterDM, labelGroupId } = Effect.runSync(buildTestChapterDM());

			Effect.runSync(chapterDM.insertTextAt(2, "XX"));

			const deleteResult = Effect.runSync(
				chapterDM.deleteLabel(labelGroupId, 0, 5).pipe(Effect.either),
			);
			expect(deleteResult._tag).toBe("Left");
		});

		it("preserves labels before insertion point", () => {
			const { chapterDM, labelGroupId } = Effect.runSync(buildTestChapterDM());

			Effect.runSync(chapterDM.insertTextAt(14, " yesterday"));

			const deleteResult = Effect.runSync(
				chapterDM.deleteLabel(labelGroupId, 0, 5).pipe(Effect.either),
			);
			expect(deleteResult._tag).toBe("Right");
		});
	});

	describe("deleteTextAt", () => {
		it("shifts labels after deletion range", () => {
			const { chapterDM, labelGroupId } = Effect.runSync(buildTestChapterDM());

			Effect.runSync(chapterDM.deleteTextAt(5, 10));

			Effect.runSync(chapterDM.flush());

			const deleteResult = Effect.runSync(
				chapterDM.deleteLabel(labelGroupId, 5, 8).pipe(Effect.either),
			);
			expect(deleteResult._tag).toBe("Right");
		});

		it("drops labels overlapping deletion range", () => {
			const { chapterDM, labelGroupId } = Effect.runSync(buildTestChapterDM());

			Effect.runSync(chapterDM.deleteTextAt(8, 14));

			const deleteResult = Effect.runSync(
				chapterDM.deleteLabel(labelGroupId, 10, 13).pipe(Effect.either),
			);
			expect(deleteResult._tag).toBe("Left");
		});
	});

	describe("destroy", () => {
		it("prevents further operations after destroy", () => {
			const { chapterDM, labelGroupId } = Effect.runSync(buildTestChapterDM());

			Effect.runSync(chapterDM.destroy());

			const result = Effect.runSync(
				chapterDM.addLabel(labelGroupId, 6, 9, "met").pipe(Effect.either),
			);
			expect(result._tag).toBe("Left");
		});
	});
});
