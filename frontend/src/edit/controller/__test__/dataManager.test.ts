import { describe, expect, it, vi } from "vitest";
import { Effect } from "effect";
import { buildChapterDataManager } from "../chapterDataManager";
import { buildIdRepository } from "../idRepository";
import { buildRequestManager } from "../requestmanager";
import { buildNovelDataManager, type NovelData } from "../novelDataManager";
import { CServId, LGServId, type IDRepository } from "../types/idTypes";
import type { TriggerEvent } from "../types/controllerTypes";
import { Prov } from "../types/helperTypes";
import { buildLabelGroupIndex } from "../dmHelpers";
import { Visibility, type Novel } from "@/api/models";
import type { Role } from "@/api/models/role";
import { RequestKey, type ReserveList } from "../types/requestTypes";
import {
	createLabelGroupLabelGroupsPost,
	readEditChapterDataEditChapterDataChapterIdPost,
	type readEditChapterDataEditChapterDataChapterIdPostResponse,
	updateChapterContentChaptersChapterIdContentPatch,
	updateLabelDataStreamLabelDatasLabelDataIdPatch,
	readEditChapterLabelDataEditChapterDataChapterIdLabelDataPost,
	type readEditChapterLabelDataEditChapterDataChapterIdLabelDataPostResponse,
} from "@/api/endpoints/default/default";

vi.mock("@/api/endpoints/default/default", async (importOriginal) => {
	const actual = await importOriginal<typeof import("@/api/endpoints/default/default")>();
	return {
		...actual,
		createLabelGroupLabelGroupsPost: vi.fn(),
		readEditChapterDataEditChapterDataChapterIdPost: vi.fn(),
		updateChapterContentChaptersChapterIdContentPatch: vi.fn(),
		updateLabelDataStreamLabelDatasLabelDataIdPatch: vi.fn(),
		readEditChapterLabelDataEditChapterDataChapterIdLabelDataPost: vi.fn(),
	};
});

const UUID1 = "00000000-0000-0000-0000-000000000001";
const UUID2 = "00000000-0000-0000-0000-000000000002";
const UUID3 = "00000000-0000-0000-0000-000000000003";
const UUID4 = "00000000-0000-0000-0000-000000000004";
const UUID5 = "00000000-0000-0000-0000-000000000005";
const UUID6 = "00000000-0000-0000-0000-000000000006";
const UUID7 = "00000000-0000-0000-0000-000000000007";
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

		const chapterId = Effect.runSync(
			idRepo.newIdAndBindId({ kind: "chapter", servId: CServId(UUID1) }),
		);
		const labelGroupProvId = Effect.runSync(
			idRepo.newIdAndBindId({ kind: "labelGroup", servId: LGServId(UUID3) }),
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

		return { chapterDM, triggerEvents, labelGroupId: labelGroupProvId, chapterId, idRepo };
	});
}

function makeNovelDataWithoutLabelGroups(): NovelData {
	return {
		novel: mockNovel,
		chapters: [
			{
				chapterId: UUID1,
				chapterNum: 1,
				chapterTitle: "Chapter 1",
				chapterIsPublic: false,
				novelId: NOVEL_ID,
			},
		],
		labelGroups: [],
		novelRole: mockRole,
		autoLabelRuns: [],
	};
}

function makeOpenChapterResponse(): readEditChapterDataEditChapterDataChapterIdPostResponse {
	return {
		status: 200,
		data: {
			chapterContent: {
				chapterContentId: UUID2,
				chapterContentText: "Alice met Bob at the park.",
				chapterContentVersion: 1,
			},
			eagerLabelData: [],
			lazyLabelData: [],
			noLabelData: [],
		},
		headers: new Headers(),
	};
}

function makeReloadResponse(
	labelDataId: string,
): readEditChapterLabelDataEditChapterDataChapterIdLabelDataPostResponse {
	return {
		status: 200,
		data: [
			{
				labelData: {
					labelDataId,
					chapterContentId: UUID2,
					labelGroupId: UUID3,
				},
				labelGroup: {
					labelGroupId: UUID3,
					labelGroupName: "Characters",
					novelId: NOVEL_ID,
				},
				labels: [
					{
						labelId: "00000000-0000-0000-0000-0000000000e0",
						labelDataId,
						labelStart: 0,
						labelEnd: 5,
						labelWord: "Alice",
						labelEntityGroup: "character",
						labelScore: 1,
						labelDirty: false,
					},
					{
						labelId: "00000000-0000-0000-0000-0000000000e1",
						labelDataId,
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
		headers: new Headers(),
	};
}

const reserveAll = (idRepo: IDRepository, reserveList: ReserveList) =>
	Effect.gen(function* () {
		for (const reservation of reserveList.autoLabel) {
			yield* idRepo.reserveIdObjState(reservation);
		}
		for (const reservation of reserveList.autoLabelRun) {
			yield* idRepo.reserveIdObjState(reservation);
		}
		for (const reservation of reserveList.chapter) {
			yield* idRepo.reserveIdObjState(reservation);
		}
		for (const reservation of reserveList.chapterContent) {
			yield* idRepo.reserveIdObjState(reservation);
		}
		for (const reservation of reserveList.label) {
			yield* idRepo.reserveIdObjState(reservation);
		}
		for (const reservation of reserveList.labelData) {
			yield* idRepo.reserveIdObjState(reservation);
		}
		for (const reservation of reserveList.labelGroup) {
			yield* idRepo.reserveIdObjState(reservation);
		}
	});

const releaseAllOnSuccess = (idRepo: IDRepository, reserveList: ReserveList) =>
	Effect.gen(function* () {
		for (const reservation of reserveList.autoLabel) {
			yield* idRepo.releaseIdObjStateOnSuccess(reservation);
		}
		for (const reservation of reserveList.autoLabelRun) {
			yield* idRepo.releaseIdObjStateOnSuccess(reservation);
		}
		for (const reservation of reserveList.chapter) {
			yield* idRepo.releaseIdObjStateOnSuccess(reservation);
		}
		for (const reservation of reserveList.chapterContent) {
			yield* idRepo.releaseIdObjStateOnSuccess(reservation);
		}
		for (const reservation of reserveList.label) {
			yield* idRepo.releaseIdObjStateOnSuccess(reservation);
		}
		for (const reservation of reserveList.labelData) {
			yield* idRepo.releaseIdObjStateOnSuccess(reservation);
		}
		for (const reservation of reserveList.labelGroup) {
			yield* idRepo.releaseIdObjStateOnSuccess(reservation);
		}
	});

async function buildOpenedNovelWithAddedLabelGroup() {
	const openChapterMock = vi.mocked(readEditChapterDataEditChapterDataChapterIdPost);
	const createLabelGroupMock = vi.mocked(createLabelGroupLabelGroupsPost);
	openChapterMock.mockClear();
	createLabelGroupMock.mockClear();
	openChapterMock.mockResolvedValue(makeOpenChapterResponse());
	createLabelGroupMock.mockResolvedValue({
		status: 200,
		data: {
			labelGroupId: UUID3,
			labelGroupName: "Characters",
			novelId: NOVEL_ID,
		},
		headers: new Headers(),
	});

	const idRepo = buildIdRepository();
	const novelDM = Effect.runSync(
		buildNovelDataManager(
			() => Effect.succeed(makeNovelDataWithoutLabelGroups()),
			() => Effect.succeed(void 0),
			idRepo,
		),
	);
	const chapterId = Effect.runSync(novelDM.getters.chapterIds())[0];
	expect(chapterId).toBeDefined();

	const openEvents = Effect.runSync(
		novelDM.openChapter(chapterId, [], {
			now: true,
			forEditor: true,
			fromCached: false,
		}),
	);
	expect(openEvents).toHaveLength(1);
	const openResponse = await Effect.runPromise(openEvents[0].send(RequestKey("open-key")));
	await Effect.runPromise(openEvents[0].postSend(openResponse));

	const addGroupEvents = Effect.runSync(novelDM.addLabelGroup("Characters"));
	expect(addGroupEvents).toHaveLength(1);
	const labelGroupId = Effect.runSync(novelDM.getters.labelGroupIds())[0];
	expect(labelGroupId).toBeDefined();

	const addGroupReserveList = addGroupEvents[0].reservationRequest.reserveList();
	Effect.runSync(reserveAll(idRepo, addGroupReserveList));
	const addGroupResponse = await Effect.runPromise(
		addGroupEvents[0].send(RequestKey("add-group-key")),
	);
	await Effect.runPromise(addGroupEvents[0].postSend(addGroupResponse));
	Effect.runSync(releaseAllOnSuccess(idRepo, addGroupReserveList));

	const chapterDM = novelDM.getChapterDM(chapterId);
	if (chapterDM === null) {
		throw new Error("Chapter data manager was not opened");
	}

	return { chapterDM, idRepo, labelGroupId };
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
			expect(chapterDM.getters.isDestroyed()).toBe(true);
		});

		it("flushes buffered work with a chapter read lock", () => {
			const { chapterDM, chapterId } = Effect.runSync(buildTestChapterDM());

			Effect.runSync(chapterDM.insertTextAt(0, "Hello "));
			const events = Effect.runSync(chapterDM.destroy());

			expect(events).toHaveLength(1);
			expect(events[0].reservationRequest.reserveList().chapter).toEqual([
				{ id: chapterId, kind: "chapter", desiredState: "locked" },
			]);
		});
	});

	describe("multiple text edits", () => {
		it("shifts labels and sends updated chapter content ID across two edits", async () => {
			const V2 = "00000000-0000-0000-0000-000000000007";
			const V3 = "00000000-0000-0000-0000-00000000000c";

			const updateChapterContentMock = vi.mocked(
				updateChapterContentChaptersChapterIdContentPatch,
			);
			updateChapterContentMock.mockClear();

			updateChapterContentMock.mockResolvedValue({
				status: 200,
				data: {
					chapterContentId: V2,
					chapterContentVersion: 2,
					labelDataIdMap: { [UUID4]: "00000000-0000-0000-0000-000000000008" },
				},
				headers: new Headers(),
			});

			const { chapterDM, labelGroupId } = Effect.runSync(buildTestChapterDM());

			Effect.runSync(chapterDM.insertTextAt(5, " first"));
			const events1 = Effect.runSync(chapterDM.flush());
			expect(events1).toHaveLength(1);

			await Effect.runPromise(events1[0].send(RequestKey("key-1")));
			console.log(
				"After first send, updateChapterContentMock calls:",
				updateChapterContentMock.mock.calls,
			);
			await Effect.runPromise(
				events1[0]
					.postSend({
						chapterContentId: V2,
						chapterContentVersion: 2,
						labelDataIdMap: {
							[UUID4]: "00000000-0000-0000-0000-000000000008",
						},
					})
					.pipe(Effect.tapError((err) => Effect.logError(`postSend failed: ${err}`))),
			);

			console.log(
				"After first postSend, updateChapterContentMock calls:",
				updateChapterContentMock.mock.calls,
			);

			const afterFirstText = Effect.runSync(chapterDM.getters.text());
			expect(afterFirstText).toBe("Alice first met Bob at the park.");

			const afterFirstSlot = Effect.runSync(chapterDM.getters.labelDataSlot(labelGroupId));
			expect(afterFirstSlot.status).toBe("ready");
			if (afterFirstSlot.status === "ready") {
				expect(
					afterFirstSlot.data.labels.map((l) => [l.labelStart, l.labelEnd, l.labelWord]),
				).toEqual([
					[0, 5, "Alice"],
					[16, 19, "Bob"],
				]);
			}

			updateChapterContentMock.mockClear();

			updateChapterContentMock.mockResolvedValue({
				status: 200,
				data: {
					chapterContentId: V3,
					chapterContentVersion: 3,
					labelDataIdMap: { [UUID4]: "00000000-0000-0000-0000-00000000000d" },
				},
				headers: new Headers(),
			});

			Effect.runSync(chapterDM.insertTextAt(10, " second"));
			const events2 = Effect.runSync(chapterDM.flush());
			expect(events2).toHaveLength(1);

			const afterSecondText = Effect.runSync(chapterDM.getters.text());
			expect(afterSecondText).toBe("Alice firs secondt met Bob at the park.");

			const afterSecondSlot = Effect.runSync(chapterDM.getters.labelDataSlot(labelGroupId));
			expect(afterSecondSlot.status).toBe("ready");
			if (afterSecondSlot.status === "ready") {
				expect(
					afterSecondSlot.data.labels.map((l) => [l.labelStart, l.labelEnd, l.labelWord]),
				).toEqual([
					[0, 5, "Alice"],
					[23, 26, "Bob"],
				]);
			}

			await Effect.runPromise(events2[0].send(RequestKey("key-2")));

			expect(updateChapterContentMock).toHaveBeenCalledTimes(1);
			expect(updateChapterContentMock).toHaveBeenCalledWith(
				UUID1,
				expect.objectContaining({
					chapterContentId: V2,
				}),
				{ requestKey: "key-2" },
			);
		});
	});

	describe("reload then text edit", () => {
		it("does not leave reloadGroup waiting after openChapter then addLabelGroup", async () => {
			const { chapterDM, labelGroupId } = await buildOpenedNovelWithAddedLabelGroup();

			const reloadEvents = Effect.runSync(chapterDM.reloadGroup(labelGroupId, true));
			expect(reloadEvents).toHaveLength(2);

			const waitResult = Effect.runSync(reloadEvents[0].reservationRequest.wait());
			expect(waitResult).toBe(false);
		});

		it("omits pending labelData from reloadGroup primary request for a newly added group", async () => {
			const { chapterDM, idRepo, labelGroupId } = await buildOpenedNovelWithAddedLabelGroup();

			const reloadEvents = Effect.runSync(chapterDM.reloadGroup(labelGroupId, true));
			expect(reloadEvents).toHaveLength(2);

			const reserveList = reloadEvents[0].reservationRequest.reserveList();
			const labelGroupReady = Effect.runSync(idRepo.isReserveable(reserveList.labelGroup[0]));
			const cleanupReserveList = reloadEvents[1].reservationRequest.reserveList();

			expect(labelGroupReady).toBe(true);
			expect(reserveList.labelData).toEqual([]);
			expect(cleanupReserveList.labelData).toEqual([
				{
					id: cleanupReserveList.labelData[0].id,
					kind: "labelData",
					desiredState: "killing",
				},
			]);
		});

		it("blocks text op reservation when reload returns same labelDataId", async () => {
			const reloadMock = vi.mocked(
				readEditChapterLabelDataEditChapterDataChapterIdLabelDataPost,
			);
			reloadMock.mockClear();

			reloadMock.mockResolvedValue(makeReloadResponse(UUID4));

			const { chapterDM, labelGroupId, idRepo } = Effect.runSync(buildTestChapterDM());

			const reloadEvents = Effect.runSync(chapterDM.reloadGroup(labelGroupId, true));
			expect(reloadEvents[0].variant).toBe("reloadGroup");

			const responseData = await Effect.runPromise(
				reloadEvents[0].send(RequestKey("reload-key")),
			);
			await Effect.runPromise(reloadEvents[0].postSend(responseData));

			const slot = Effect.runSync(chapterDM.getters.labelDataSlot(labelGroupId));
			expect(slot.status).toBe("ready");
			const labelDataProvId = slot.meta.labelData.labelDataId;

			const isReserveableResult = Effect.runSync(
				idRepo.isReserveable({
					kind: "labelData",
					id: labelDataProvId,
					desiredState: "idUpdating",
				}),
			);
			expect(isReserveableResult).toBe(true);

			Effect.runSync(chapterDM.insertTextAt(5, " first"));
			const textEvents = Effect.runSync(chapterDM.flush());
			expect(textEvents).toHaveLength(1);

			const waitResult = Effect.runSync(textEvents[0].reservationRequest.wait());
			expect(waitResult).toBe(false);
		});

		it("drains reload cleanup after the primary reload request releases its locks", async () => {
			const reloadMock = vi.mocked(
				readEditChapterLabelDataEditChapterDataChapterIdLabelDataPost,
			);
			reloadMock.mockClear();
			reloadMock.mockResolvedValue(makeReloadResponse(UUID7));

			const { chapterDM, labelGroupId, idRepo } = Effect.runSync(buildTestChapterDM());
			const requestManager = Effect.runSync(
				buildRequestManager(idRepo, () => Effect.succeed(void 0)),
			);

			const reloadEvents = Effect.runSync(chapterDM.reloadGroup(labelGroupId, true));
			expect(reloadEvents).toHaveLength(2);
			for (const event of reloadEvents) {
				requestManager.enqueueRequest(event);
			}

			const flushResult = await Effect.runPromise(
				Effect.either(requestManager.waitFlush().pipe(Effect.timeout("500 millis"))),
			);

			expect(flushResult._tag).toBe("Right");
			expect(requestManager.isQueueEmpty()).toBe(true);
		});

		it("allows the reload cleanup request to reserve after primary reload success", async () => {
			const reloadMock = vi.mocked(
				readEditChapterLabelDataEditChapterDataChapterIdLabelDataPost,
			);
			reloadMock.mockClear();
			reloadMock.mockResolvedValue(makeReloadResponse(UUID7));

			const { chapterDM, labelGroupId, idRepo } = Effect.runSync(buildTestChapterDM());

			const reloadEvents = Effect.runSync(chapterDM.reloadGroup(labelGroupId, true));
			expect(reloadEvents).toHaveLength(2);

			const primaryReload = reloadEvents[0];
			const cleanupReload = reloadEvents[1];
			const primaryReserveList = primaryReload.reservationRequest.reserveList();

			Effect.runSync(reserveAll(idRepo, primaryReserveList));
			const responseData = await Effect.runPromise(
				primaryReload.send(RequestKey("reload-key")),
			);
			await Effect.runPromise(primaryReload.postSend(responseData));
			Effect.runSync(releaseAllOnSuccess(idRepo, primaryReserveList));

			const cleanupWaitResult = Effect.runSync(cleanupReload.reservationRequest.wait());
			expect(cleanupWaitResult).toBe(false);
		});

		it("drains a pending label op followed by reload and cleanup", async () => {
			const labelOpMock = vi.mocked(updateLabelDataStreamLabelDatasLabelDataIdPatch);
			const reloadMock = vi.mocked(
				readEditChapterLabelDataEditChapterDataChapterIdLabelDataPost,
			);
			labelOpMock.mockClear();
			reloadMock.mockClear();
			labelOpMock.mockResolvedValue({
				status: 204,
				data: undefined,
				headers: new Headers(),
			});
			reloadMock.mockResolvedValue(makeReloadResponse(UUID7));

			const { chapterDM, labelGroupId, idRepo } = Effect.runSync(buildTestChapterDM());
			const requestManager = Effect.runSync(
				buildRequestManager(idRepo, () => Effect.succeed(void 0)),
			);

			Effect.runSync(chapterDM.addLabel(labelGroupId, 6, 9, "met"));
			const reloadEvents = Effect.runSync(chapterDM.reloadGroup(labelGroupId, true));
			expect(reloadEvents.map((event) => event.variant)).toEqual([
				"labelOp",
				"reloadGroup",
				"reloadGroup",
			]);

			for (const event of reloadEvents) {
				requestManager.enqueueRequest(event);
			}

			const flushResult = await Effect.runPromise(
				Effect.either(requestManager.waitFlush().pipe(Effect.timeout("500 millis"))),
			);

			expect(flushResult._tag).toBe("Right");
			expect(requestManager.isQueueEmpty()).toBe(true);
			expect(labelOpMock).toHaveBeenCalledTimes(1);
			expect(reloadMock).toHaveBeenCalledTimes(1);
		});
	});
});

describe("buildNovelDataManager chapter eviction", () => {
	it("evicts a ready chapter and allows a fresh reopen", async () => {
		const triggerEvents: TriggerEvent[] = [];
		const novelDM = Effect.runSync(
			buildNovelDataManager(
				() => Effect.succeed(makeNovelDataWithoutLabelGroups()),
				(_getters, event) =>
					Effect.sync(() => {
						triggerEvents.push(event);
					}),
				buildIdRepository(),
			),
		);
		const chapterId = Effect.runSync(novelDM.getters.chapterIds())[0];
		const openEvents = Effect.runSync(
			novelDM.openChapter(chapterId, [], {
				now: true,
				forEditor: true,
				fromCached: false,
			}),
		);
		await Effect.runPromise(openEvents[0].postSend(makeOpenChapterResponse().data));
		expect(novelDM.getChapterDM(chapterId)).not.toBeNull();

		const closeEvents = Effect.runSync(novelDM.closeChapter(chapterId));

		expect(closeEvents).toHaveLength(1);
		expect(closeEvents[0].variant).toBe("closeChapter");
		expect(closeEvents[0].reservationRequest.reserveList().chapter).toEqual([
			{ id: chapterId, kind: "chapter", desiredState: "updating" },
		]);
		expect(novelDM.getChapterDM(chapterId)).toBeNull();
		expect(Effect.runSync(novelDM.getters.chapterGetterSlot(chapterId)).status).toBe(
			"loading",
		);
		expect(Effect.runSync(novelDM.closeChapter(chapterId))).toEqual([]);
		expect(
			Effect.runSync(
				novelDM
					.openChapter(chapterId, [], {
						now: true,
						forEditor: true,
						fromCached: true,
					})
					.pipe(Effect.either),
			)._tag,
		).toBe("Left");
		expect(triggerEvents).not.toContainEqual({ eventType: "chapterClosed", chapterId });

		Effect.runSync(closeEvents[0].preSend());

		expect(Effect.runSync(novelDM.getters.chapterGetterSlot(chapterId)).status).toBe("idle");
		expect(triggerEvents).toContainEqual({ eventType: "chapterClosed", chapterId });

		const reopenEvents = Effect.runSync(
			novelDM.openChapter(chapterId, [], {
				now: true,
				forEditor: true,
				fromCached: true,
			}),
		);
		expect(reopenEvents).toHaveLength(1);
	});

	it("orders eviction after requests flushed by destroy", async () => {
		const idRepo = buildIdRepository();
		const novelDM = Effect.runSync(
			buildNovelDataManager(
				() => Effect.succeed(makeNovelDataWithoutLabelGroups()),
				() => Effect.succeed(void 0),
				idRepo,
			),
		);
		const chapterId = Effect.runSync(novelDM.getters.chapterIds())[0];
		const openEvents = Effect.runSync(
			novelDM.openChapter(chapterId, [], {
				now: true,
				forEditor: true,
				fromCached: false,
			}),
		);
		await Effect.runPromise(openEvents[0].postSend(makeOpenChapterResponse().data));
		const chapterDM = novelDM.getChapterDM(chapterId);
		if (chapterDM === null) throw new Error("Expected an open chapter data manager");

		Effect.runSync(chapterDM.insertTextAt(0, "Hello "));
		const closeEvents = Effect.runSync(novelDM.closeChapter(chapterId));
		expect(closeEvents.map((event) => event.variant)).toEqual(["textOp", "closeChapter"]);

		const editRequest = closeEvents[0];
		const closeRequest = closeEvents[1];
		const chapterLock = editRequest.reservationRequest.reserveList().chapter[0];
		if (chapterLock === undefined || closeRequest === undefined) {
			throw new Error("Expected an edit request followed by a close request");
		}

		Effect.runSync(idRepo.reserveIdObjState(chapterLock));
		expect(Effect.runSync(closeRequest.reservationRequest.wait())).toBe(true);
		Effect.runSync(idRepo.releaseIdObjStateOnSuccess(chapterLock));
		expect(Effect.runSync(closeRequest.reservationRequest.wait())).toBe(false);
	});

	it("disposes a chapter load that is closed before sending", () => {
		const triggerEvents: TriggerEvent[] = [];
		const novelDM = Effect.runSync(
			buildNovelDataManager(
				() => Effect.succeed(makeNovelDataWithoutLabelGroups()),
				(_getters, event) =>
					Effect.sync(() => {
						triggerEvents.push(event);
					}),
				buildIdRepository(),
			),
		);
		const chapterId = Effect.runSync(novelDM.getters.chapterIds())[0];
		const openEvents = Effect.runSync(
			novelDM.openChapter(chapterId, [], {
				now: true,
				forEditor: true,
				fromCached: false,
			}),
		);

		const closeEvents = Effect.runSync(novelDM.closeChapter(chapterId));
		expect(closeEvents).toHaveLength(1);
		expect(openEvents[0].reservationRequest.skip()).toBe(false);
		expect(openEvents[0].reservationRequest.reserveList().chapter).toEqual([
			{ id: chapterId, kind: "chapter", desiredState: "locked" },
		]);
		expect(closeEvents[0].reservationRequest.reserveList().chapter).toEqual([
			{ id: chapterId, kind: "chapter", desiredState: "updating" },
		]);

		Effect.runSync(openEvents[0].postSend(makeOpenChapterResponse().data));
		expect(closeEvents[0].reservationRequest.skip()).toBe(false);
		Effect.runSync(closeEvents[0].preSend());

		expect(Effect.runSync(novelDM.getters.chapterGetterSlot(chapterId)).status).toBe("idle");
		expect(triggerEvents).toContainEqual({ eventType: "chapterClosed", chapterId });
	});
});
