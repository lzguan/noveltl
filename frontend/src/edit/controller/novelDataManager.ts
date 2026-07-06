import { Effect, Schema } from "effect";
import {
	buildChapterIndex,
	buildLabelGroupIndex,
	buildRequestQueueDispatcher,
	type ChapterIndex,
	type LabelGroupIndex,
} from "./dmHelpers";
import {
	AlreadyOpenException,
	ConnectionException,
	DuplicateChapterNumException,
	FatalException,
	LoadingException,
	NotFoundException,
} from "./types/errors";
import { TimeoutException, UnknownException } from "effect/Cause";
import type { NovelGetters, TriggerEvent } from "./types/controllerTypes";
import {
	CProvId,
	CServId,
	type IDRepository,
	LGProvId,
	LGServId,
	type ProvChapter,
	type ProvLabelGroup,
} from "./types/idTypes";
import { makeReservationRequest, Prov } from "./types/helperTypes";
import type { AutoLabelRunOutput, Chapter, LabelGroup, LabelRole, Novel } from "@/api/models";
import type { RequestEvent } from "./types/requestTypes";
import {
	CreateChapterNovelsNovelIdChaptersPost200Response,
	CreateLabelGroupLabelGroupsPost200Response,
	ReadEditChapterDataEditChapterDataChapterIdPost200Response,
} from "@/api/endpoints/default/default.effect";
import {
	createChapterNovelsNovelIdChaptersPost,
	createLabelGroupLabelGroupsPost,
	readEditChapterDataEditChapterDataChapterIdPost,
} from "@/api/endpoints/default/default";
import type { Role } from "@/api/models/role";
import type { ChapterDataManager, NovelDataManager } from "./types/dataTypes";
import { buildChapterDataManager } from "./chapterDataManager";
import { buildAutolabelDataManager } from "./autolabelDataManager";

export type NovelData = {
	novel: Novel;
	chapters: Chapter[];
	labelGroups: { labelGroup: LabelGroup; role: LabelRole }[];
	novelRole: Role;
	autoLabelRuns: AutoLabelRunOutput[];
};

export const buildNovelDataManager = (
	fetchNovelData: () => Effect.Effect<NovelData, ConnectionException | TimeoutException>,
	raiseTriggerEvent: (getters: NovelGetters, event: TriggerEvent) => Effect.Effect<void>,
	idRepo: IDRepository,
): Effect.Effect<NovelDataManager, ConnectionException | TimeoutException | FatalException> =>
	Effect.gen(function* () {
		const novelData = yield* fetchNovelData();

		const chaptersIndex: ChapterIndex = yield* buildChapterIndex(
			novelData.chapters.map<[CProvId, { chapter: ProvChapter }]>((val) => {
				const newIdExit = Effect.runSyncExit(
					idRepo.newIdAndBindId({
						kind: "chapter",
						servId: CServId(val.chapterId),
					}),
				);
				if (newIdExit._tag === "Failure") {
					throw new FatalException({
						orig: newIdExit.cause,
					});
				}
				const newId = newIdExit.value;
				return [newId, { chapter: Prov({ ...val, chapterId: newId }) }];
			}),
		);
		const labelGroupsIndex: LabelGroupIndex = yield* buildLabelGroupIndex(
			novelData.labelGroups.map<[LGProvId, { labelGroup: ProvLabelGroup; role: LabelRole }]>(
				(val) => {
					const newIdExit = Effect.runSyncExit(
						idRepo.newIdAndBindId({
							kind: "labelGroup",
							servId: LGServId(val.labelGroup.labelGroupId),
						}),
					);
					if (newIdExit._tag === "Failure") {
						throw new FatalException({
							orig: newIdExit.cause,
						});
					}
					const newId = newIdExit.value;
					return [
						newId,
						{
							labelGroup: Prov({ ...val.labelGroup, labelGroupId: newId }),
							role: val.role,
						},
					];
				},
			),
		);

		const { decorate, flush: _flush } = buildRequestQueueDispatcher<RequestEvent>();

		const flush: () => Effect.Effect<RequestEvent[], UnknownException> = () =>
			Effect.gen(function* () {
				const events = yield* _flush();
				for (const chapterId of yield* chaptersIndex.getIds()) {
					const slot = yield* chaptersIndex
						.get(chapterId)
						.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
					if (slot.status === "ready") {
						const flushResult = yield* slot.data.chapterData.flush();
						events.push(...flushResult);
					}
				}
				return events;
			});

		const getters: NovelGetters = {
			novel: () => Effect.succeed(novelData.novel),
			role: () => Effect.succeed(novelData.novelRole),
			labelGroupIds: () => labelGroupsIndex.getIds(),
			chapterIds: () => chaptersIndex.getIds(),
			chapterGetterSlot: (chapterId: CProvId) =>
				chaptersIndex.get(chapterId).pipe(
					Effect.map((slot) => {
						if (slot.status !== "ready") {
							return slot;
						} else {
							const chapterGetters = slot.data.chapterData.getters;
							return { ...slot, data: { chapterGetters, status: slot.status } };
						}
					}),
				),
			labelGroupSlot: (labelGroupId: LGProvId) => labelGroupsIndex.get(labelGroupId),
		};

		const _addLabelGroup = (
			labelGroupName: string,
		): Effect.Effect<RequestEvent[], UnknownException> =>
			Effect.gen(function* () {
				const newId = idRepo.newId("labelGroup");
				const newLabelGroup: ProvLabelGroup = Prov({
					labelGroupId: newId,
					labelGroupName,
					novelId: novelData.novel.novelId,
				});
				yield* labelGroupsIndex
					.new(newId, { labelGroup: newLabelGroup, role: "owner" })
					.pipe(
						Effect.mapError(
							() =>
								new UnknownException({
									message: "Failed to add label group to index",
								}),
						),
					);
				yield* labelGroupsIndex.increment(newId).pipe(
					Effect.mapError(
						() =>
							new UnknownException({
								message: "Failed to increment label group index",
							}),
					),
				);
				yield* raiseTriggerEvent(getters, {
					eventType: "labelGroupAdded",
					labelGroup: newLabelGroup,
				});
				const onError = (): Effect.Effect<void> => {
					return labelGroupsIndex
						.decrement(newId)
						.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
				};

				return [
					{
						cached: false,
						reservationRequest: makeReservationRequest(idRepo, {
							labelGroup: [
								{
									id: newId,
									desiredState: "creating",
									kind: "labelGroup",
								},
							],
							label: [],
							autoLabel: [],
							autoLabelRun: [],
							chapter: [],
							chapterContent: [],
							labelData: [],
						}),
						variant: "addLabelGroup",
						onFailure: onError,
						onFatalError: onError,
						retries: 3,
						active: true,
						preSend: () => {
							return Effect.succeed(void 0);
						},
						send: () =>
							Effect.gen(function* () {
								const resp = yield* Effect.tryPromise(() =>
									createLabelGroupLabelGroupsPost({
										labelGroupName,
										novelId: novelData.novel.novelId,
									}),
								).pipe(
									Effect.mapError(
										(err) =>
											new ConnectionException({
												orig: err,
											}),
									),
								);
								if (resp.status !== 200) {
									return yield* Effect.fail(
										new FatalException({
											orig: new Error(
												`Failed to create label group: ${resp}`,
											),
										}),
									);
								} else {
									return resp.data;
								}
							}),
						postSend: (data) =>
							Effect.gen(function* () {
								const validated = yield* Schema.validate(
									CreateLabelGroupLabelGroupsPost200Response,
								)(data);
								yield* idRepo.bindServerId({
									kind: "labelGroup",
									provId: newId,
									servId: LGServId(validated.labelGroupId),
								});
								yield* labelGroupsIndex.decrement(newId);
							}).pipe(Effect.mapError((err) => new FatalException({ orig: err }))),
					},
				];
			});
		const addLabelGroup = decorate(_addLabelGroup);

		const _addChapter = (
			chapterNum: number,
			chapterTitle: string,
			chapterIsPublic: boolean,
		): Effect.Effect<RequestEvent[], UnknownException | DuplicateChapterNumException> =>
			Effect.gen(function* () {
				const newId = idRepo.newId("chapter");
				const newChapter: ProvChapter = Prov({
					chapterId: newId,
					chapterNum,
					chapterTitle,
					chapterIsPublic,
					novelId: novelData.novel.novelId,
				});
				if (novelData.novelRole === "viewer") {
					return yield* Effect.fail(
						new UnknownException({ message: "Viewer role cannot add chapter" }),
					);
				}
				yield* chaptersIndex.new(newId, { chapter: newChapter }).pipe(
					Effect.mapError((err) => {
						if (err._tag === "DuplicateChapterNumException") return err;
						return new UnknownException({ message: "Failed to add chapter to index" });
					}),
				);
				yield* chaptersIndex.increment(newId).pipe(
					Effect.mapError(
						() =>
							new UnknownException({
								message: "Failed to increment chapter index",
							}),
					),
				);
				yield* raiseTriggerEvent(getters, {
					eventType: "chapterAdded",
					chapter: newChapter,
				});
				const onError = (): Effect.Effect<void> => {
					return chaptersIndex
						.decrement(newId)
						.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
				};
				return [
					{
						cached: false,
						reservationRequest: makeReservationRequest(idRepo, {
							labelGroup: [],
							label: [],
							autoLabel: [],
							autoLabelRun: [],
							chapter: [
								{
									id: newId,
									desiredState: "creating",
									kind: "chapter",
								},
							],
							chapterContent: [],
							labelData: [],
						}),
						variant: "addChapter",
						onFailure: onError,
						onFatalError: onError,
						retries: 3,
						active: true,
						preSend: () => {
							return Effect.succeed(void 0);
						},
						send: () =>
							Effect.gen(function* () {
								const resp = yield* Effect.tryPromise(() =>
									createChapterNovelsNovelIdChaptersPost(
										novelData.novel.novelId,
										{
											chapterNum,
											chapterTitle,
											chapterIsPublic,
										},
									),
								).pipe(
									Effect.mapError(
										(err) =>
											new ConnectionException({
												orig: err,
											}),
									),
								);
								if (resp.status !== 200) {
									return yield* Effect.fail(
										new FatalException({
											orig: new Error(`Failed to create chapter: ${resp}`),
										}),
									);
								} else {
									return resp.data;
								}
							}),
						postSend: (data) =>
							Effect.gen(function* () {
								const validated = yield* Schema.validate(
									CreateChapterNovelsNovelIdChaptersPost200Response,
								)(data);
								yield* idRepo.bindServerId({
									kind: "chapter",
									provId: newId,
									servId: CServId(validated.metadata.chapterId),
								});
								yield* chaptersIndex.decrement(newId);
							}).pipe(Effect.mapError((err) => new FatalException({ orig: err }))),
					},
				];
			});
		const addChapter = decorate(_addChapter);

		const _openChapter = (
			chapterId: CProvId,
			eager: LGProvId[],
			forEditor: boolean,
		): Effect.Effect<
			RequestEvent[],
			AlreadyOpenException | NotFoundException | LoadingException | UnknownException
		> =>
			Effect.gen(function* () {
				const chapter = yield* chaptersIndex.get(chapterId);
				if (chapter.status === "ready") {
					return yield* Effect.fail(new AlreadyOpenException({ id: chapterId }));
				}
				if (chapter.status === "loading") {
					return yield* Effect.fail(new LoadingException({ id: chapterId }));
				}
				yield* chaptersIndex.setData(chapterId, { status: "loading" });
				return [
					{
						cached: false,
						variant: "openChapter",
						reservationRequest: makeReservationRequest(idRepo, {
							labelGroup: [],
							label: [],
							autoLabel: [],
							autoLabelRun: [],
							chapter: [
								{
									id: chapterId,
									desiredState: "locked",
									kind: "chapter",
								},
							],
							chapterContent: [],
							labelData: [],
						}),
						onFailure: () =>
							chaptersIndex
								.setData(chapterId, { status: "error" })
								.pipe(Effect.catchAll(() => Effect.succeed(void 0))),
						onFatalError: () =>
							chaptersIndex
								.setData(chapterId, { status: "error" })
								.pipe(Effect.catchAll(() => Effect.succeed(void 0))),
						retries: 3,
						active: false,
						preSend: () => Effect.succeed(void 0),
						send: () =>
							Effect.gen(function* () {
								const chapterServId = yield* idRepo
									.getServerId({ kind: "chapter", provId: chapterId })
									.pipe(
										Effect.mapError((err) => new FatalException({ orig: err })),
									);
								const esi = yield* Effect.all(
									eager.map((id) =>
										idRepo.getServerId({ kind: "labelGroup", provId: id }),
									),
								).pipe(Effect.mapError((err) => new FatalException({ orig: err })));
								const eagerServIds = esi.filter((id) => id !== null);
								if (chapterServId === null) {
									return yield* Effect.fail(
										new FatalException({
											orig: new Error(
												`Unexpected: chapter ${chapterId} does not have a server id`,
											),
										}),
									);
								}
								const resp = yield* Effect.tryPromise(async () => {
									const inResp =
										await readEditChapterDataEditChapterDataChapterIdPost(
											chapterServId,
											eagerServIds,
										);
									return inResp;
								}).pipe(
									Effect.mapError(
										(err) => new ConnectionException({ orig: err }),
									),
								);
								if (resp.status !== 200) {
									return yield* Effect.fail(
										new FatalException({
											orig: new Error(
												`Failed to read chapter data: ${resp.status}`,
											),
										}),
									);
								}
								return resp.data;
							}),
						postSend: (resp: unknown) =>
							Effect.gen(function* () {
								const validated = yield* Schema.validate(
									ReadEditChapterDataEditChapterDataChapterIdPost200Response,
								)(resp).pipe(
									Effect.mapError((err) => new FatalException({ orig: err })),
								);
								const chapterDataManager = yield* buildChapterDataManager(
									validated,
									chapterId,
									(event) => raiseTriggerEvent(getters, event),
									idRepo,
									{
										labelGroupIds: () => labelGroupsIndex.getIds(),
										labelGroup: (labelGroupId) =>
											labelGroupsIndex.get(labelGroupId),
										novel: () => Effect.succeed(novelData.novel),
										role: () => Effect.succeed(novelData.novelRole),
									},
								).pipe(Effect.mapError((err) => new FatalException({ orig: err })));
								yield* chaptersIndex
									.setData(chapterId, {
										status: "ready",
										data: {
											chapterData: chapterDataManager,
										},
									})
									.pipe(
										Effect.mapError((err) => new FatalException({ orig: err })),
									);
								yield* raiseTriggerEvent(getters, {
									eventType: "chapterOpened",
									chapterId,
									flags: { forEditor },
								});
							}),
					},
				];
			});
		const openChapter = (
			chapterId: CProvId,
			eager: LGProvId[],
			flags: ({ now: boolean; forEditor: false } | { now: true; forEditor: true }) & {
				fromCached: boolean;
			},
		) => {
			const noCachedEffect = Effect.gen(function* () {
				const reqEvents = yield* decorate(_openChapter)(chapterId, eager, flags.forEditor);
				if (flags.now) {
					const flushEvents = yield* flush();
					reqEvents.push(...flushEvents);
				}
				return reqEvents;
			});
			return Effect.if(
				Effect.gen(function* () {
					const chapterSlot = yield* chaptersIndex.get(chapterId);
					return chapterSlot.status === "ready" && flags.fromCached;
				}),
				{
					onTrue: () =>
						raiseTriggerEvent(getters, {
							eventType: "chapterOpened",
							chapterId,
							flags,
						}).pipe(Effect.andThen(() => Effect.succeed<RequestEvent[]>([]))),
					onFalse: () => noCachedEffect,
				},
			);
		};
		const getChapterDM = (id: CProvId): ChapterDataManager | null => {
			const slot = Effect.runSync(
				chaptersIndex.get(id).pipe(Effect.catchAll(() => Effect.succeed(null))),
			);
			if (!slot || slot.status !== "ready" || !slot.data) return null;
			return slot.data.chapterData;
		};

		const autolabelDM = yield* buildAutolabelDataManager(
			novelData.novel.novelId,
			(event) => raiseTriggerEvent(getters, event),
			idRepo,
			{
				chapterIds: () => chaptersIndex.getIds(),
				chapter: (chId) =>
					chaptersIndex.get(chId).pipe(
						Effect.andThen((slot) =>
							Effect.gen(function* () {
								return {
									chapterNum: slot.meta.chapter.chapterNum,
									chapterIsPublic: slot.meta.chapter.chapterIsPublic,
									cc:
										slot.status === "ready"
											? {
													status: "ready" as const,
													chapterContentId:
														yield* slot.data.chapterData.getters.chapterContentId(),
												}
											: { status: slot.status },
								};
							}),
						),
					),
			},
			novelData.autoLabelRuns,
		);

		return {
			addLabelGroup,
			addChapter,
			openChapter,
			flush,
			getChapterDM,
			createAutoLabelRun: autolabelDM.createAutoLabelRun,
			promoteAutoLabelRun: autolabelDM.promoteAutoLabelRun,
			refreshAutoLabelRuns: autolabelDM.refreshAutoLabelRuns,
			reloadAutoLabelRun: autolabelDM.reloadAutoLabelRun,
			loadAutoLabelData: autolabelDM.loadAutoLabelData,
			getters,
		};
	});
