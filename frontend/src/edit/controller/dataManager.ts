import { Effect, Schema } from "effect";
import {
	buildChapterIndex,
	buildLabelDataIndex,
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
	type IDRepository,
	type InFlightIdStatus,
	LDProvId,
	LGProvId,
	LProvId,
	type ProvChapter,
	type ProvLabel,
	type ProvLabelGroup,
	ServId,
} from "./types/idTypes";
import {
	IdempotentCallable,
	isAllReserveable,
	makeReservationRequest,
	Prov,
	type LabelGroupSlot,
} from "./types/helperTypes";
import type { Chapter, LabelGroup, LabelRole, Novel, TextOp } from "@/api/models";
import type { RequestEvent, Reservation, ReserveList } from "./types/requestTypes";
import type { LabelOp } from "./types/dataTypes";
import {
	CreateChapterNovelsNovelIdChaptersPost200Response,
	CreateLabelGroupLabelGroupsPost200Response,
	ReadEditChapterDataEditChapterDataChapterIdGet200Response,
	ReadEditChapterLabelDataEditChapterDataChapterIdLabelDataGet200Response,
	UpdateChapterContentChaptersChapterIdContentPatch200Response,
} from "@/api/endpoints/default/default.effect";
import {
	createChapterNovelsNovelIdChaptersPost,
	createLabelGroupLabelGroupsPost,
	readEditChapterDataEditChapterDataChapterIdGet,
	readEditChapterLabelDataEditChapterDataChapterIdLabelDataGet,
	updateChapterContentChaptersChapterIdContentPatch,
	updateLabelDataStreamLabelDatasLabelDataIdPatch,
} from "@/api/endpoints/default/default";
import type { Role } from "@/api/models/role";
import type { ChapterDataManager, NovelDataManager } from "./types/dataTypes";

export type NovelData = {
	novel: Novel;
	chapters: Chapter[];
	labelGroups: { labelGroup: LabelGroup; role: LabelRole }[];
	novelRole: Role;
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
				const newId = idRepo.newIdAndBindId("chapter", ServId(val.chapterId));
				return [newId, { chapter: Prov({ ...val, chapterId: newId }) }];
			}),
		);
		const labelGroupsIndex: LabelGroupIndex = yield* buildLabelGroupIndex(
			novelData.labelGroups.map<[LGProvId, { labelGroup: ProvLabelGroup; role: LabelRole }]>(
				(val) => {
					const newId = idRepo.newIdAndBindId(
						"labelGroup",
						ServId(val.labelGroup.labelGroupId),
					);
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

		const { decorate, flush } = buildRequestQueueDispatcher<RequestEvent>();

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
								yield* idRepo.bindServerId(
									"labelGroup",
									newId,
									ServId(validated.labelGroupId),
								);
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
								yield* idRepo.bindServerId(
									"chapter",
									newId,
									ServId(validated.metadata.chapterId),
								);
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
									.getServerId("chapter", chapterId)
									.pipe(
										Effect.mapError((err) => new FatalException({ orig: err })),
									);
								const esi = yield* Effect.all(
									eager.map((id) => idRepo.getServerId("labelGroup", id)),
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
										await readEditChapterDataEditChapterDataChapterIdGet(
											chapterServId,
											eager.length > 0
												? {
														eager: eagerServIds,
													}
												: undefined,
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
									ReadEditChapterDataEditChapterDataChapterIdGet200Response,
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

		return {
			addLabelGroup,
			addChapter,
			openChapter,
			flush,
			getChapterDM,
			getters,
		};
	});

export const buildChapterDataManager = (
	editChapterData: typeof ReadEditChapterDataEditChapterDataChapterIdGet200Response.Type,
	chapterId: CProvId,
	raiseTriggerEvent: (event: TriggerEvent) => Effect.Effect<void>,
	idRepo: IDRepository,
	getters: {
		labelGroupIds: () => Effect.Effect<LGProvId[], UnknownException>;
		labelGroup: (labelGroupId: LGProvId) => Effect.Effect<LabelGroupSlot, NotFoundException>;
		novel: () => Effect.Effect<Novel>;
		role: () => Effect.Effect<Role>;
	},
): Effect.Effect<ChapterDataManager, UnknownException> =>
	Effect.gen(function* () {
		const chapterContentId = idRepo.newIdAndBindId(
			"chapterContent",
			ServId(editChapterData.chapterContent.chapterContentId),
		);
		let text = editChapterData.chapterContent.chapterContentText;

		const labelDataIndex = yield* buildLabelDataIndex().pipe(
			Effect.mapError((err) => new UnknownException({ orig: err })),
		);
		// scoped for initialization
		{
			const labelGroupProvIds = yield* getters.labelGroupIds();
			const lgStoP = new Map<ServId, LGProvId>();
			for (const lgProvId of labelGroupProvIds) {
				const lgSlot = yield* getters
					.labelGroup(lgProvId)
					.pipe(Effect.catchAll(() => Effect.succeed(null)));
				if (!lgSlot) {
					continue;
				}
				const lgServId = yield* idRepo
					.getServerId("labelGroup", lgSlot.meta.labelGroup.labelGroupId)
					.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
				if (lgServId === null) {
					return yield* Effect.fail(
						new UnknownException({
							message: `Unexpected: label group ${lgProvId} does not have a server id`,
						}),
					);
				}
				lgStoP.set(lgServId, lgProvId);
			}

			for (const entry of editChapterData.eagerLabelData) {
				const provLdId = idRepo.newIdAndBindId(
					"labelData",
					ServId(entry.labelData.labelDataId),
				);
				const provLabels: ProvLabel[] = entry.labels
					.map((l) => {
						const provLabelId = idRepo.newIdAndBindExists("label");
						return Prov({
							...l,
							labelId: provLabelId,
							labelDataId: provLdId,
						});
					})
					.sort((a, b) => a.labelStart - b.labelStart);
				const servId = ServId(entry.labelGroup.labelGroupId);
				const lgProvId = lgStoP.get(servId);
				if (!lgProvId) {
					return yield* Effect.fail(
						new UnknownException({
							message: `Unexpected: label group with server id ${servId} not found in label group index`,
						}),
					);
				}
				yield* labelDataIndex
					.new(lgProvId, {
						labelData: Prov({
							labelDataId: provLdId,
							labelGroupId: lgProvId,
							chapterContentId: chapterContentId,
						}),
					})
					.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
				yield* labelDataIndex
					.setData(lgProvId, {
						status: "ready",
						data: { labels: provLabels },
					})
					.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
			}

			for (const entry of editChapterData.lazyLabelData) {
				const provLdId = idRepo.newIdAndBindId(
					"labelData",
					ServId(entry.labelData.labelDataId),
				);
				const servId = ServId(entry.labelGroup.labelGroupId);
				const lgProvId = lgStoP.get(servId);
				if (!lgProvId) {
					return yield* Effect.fail(
						new UnknownException({
							message: `Unexpected: label group with server id ${servId} not found in label group index`,
						}),
					);
				}
				yield* labelDataIndex
					.new(lgProvId, {
						labelData: Prov({
							labelDataId: provLdId,
							labelGroupId: lgProvId,
							chapterContentId: chapterContentId,
						}),
					})
					.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
			}
		}

		// Op queue: keyed by labelGroupProvId for label ops.
		// Only one tag can be active at a time. Tag switching is handled by auto-flush in actions.
		let opQueue:
			| { tag: "label"; queue: Map<LGProvId, { labelId: LProvId; op: LabelOp }[]> }
			| { tag: "text"; queue: TextOp[] }
			| { tag: "neither" } = { tag: "neither" };

		let destroyed = false;

		const { decorate, flush: dispatcherFlush } = buildRequestQueueDispatcher<RequestEvent>();

		const buildLabelReservations = (
			ops: { labelId: LProvId; op: LabelOp }[],
		): Reservation<"label">[] => {
			const map = new Map<LProvId, InFlightIdStatus>();
			for (const { labelId, op } of ops) {
				const id = labelId;
				if (op.op === "add") {
					map.set(id, "creating");
				} else if (op.op === "update") {
					if (map.get(id) !== "creating") {
						map.set(id, "updating");
					}
				} else if (op.op === "delete") {
					if (map.get(id) === "creating") {
						map.set(id, "killing");
					} else {
						map.set(id, "deleting");
					}
				}
			}
			return Array.from(map.entries()).map(([id, desiredState]) => ({
				id,
				kind: "label",
				desiredState,
			}));
		};

		const _flush = (): Effect.Effect<RequestEvent[], UnknownException> =>
			Effect.gen(function* () {
				if (opQueue.tag === "label") {
					const events: RequestEvent[] = [];
					for (const [labelGroupProvId, ops] of opQueue.queue) {
						if (ops.length === 0) continue;
						const slot = yield* labelDataIndex.get(labelGroupProvId).pipe(
							Effect.mapError(
								() =>
									new UnknownException({
										message: "Label group not found in index",
									}),
							),
						);
						const labelDataProvId = slot.meta.labelData.labelDataId;
						const opsSnapshot = [...ops];
						const labelOpReserveList: ReserveList = {
							labelData: [
								{
									id: labelDataProvId,
									kind: "labelData",
									desiredState: "updating",
								},
							],
							chapterContent: [
								{
									id: chapterContentId,
									kind: "chapterContent",
									desiredState: "locked",
								},
							],
							label: buildLabelReservations(opsSnapshot),
							chapter: [],
							labelGroup: [],
						};
						events.push({
							cached: false,
							variant: "labelOp",
							active: true,
							retries: 3,
							reservationRequest: {
								reserveList: IdempotentCallable(() => labelOpReserveList),
								skip: () => false,
								wait: () =>
									isAllReserveable(idRepo, labelOpReserveList).pipe(
										Effect.map((ready) => !ready),
									),
							},
							onFailure: () => Effect.succeed(void 0),
							onFatalError: () => Effect.succeed(void 0),
							preSend: () => Effect.succeed(void 0),
							send: () =>
								Effect.gen(function* () {
									const servLdId = yield* idRepo
										.getServerId("labelData", labelDataProvId)
										.pipe(
											Effect.mapError(
												(err) => new FatalException({ orig: err }),
											),
										);
									if (!servLdId) {
										return yield* Effect.fail(
											new FatalException({
												orig: new Error("Label data has no server ID"),
											}),
										);
									}
									const resp = yield* Effect.tryPromise(() =>
										updateLabelDataStreamLabelDatasLabelDataIdPatch(servLdId, {
											ops: opsSnapshot.map(({ op }) => op),
										}),
									).pipe(
										Effect.mapError(
											(err) => new ConnectionException({ orig: err }),
										),
									);
									if (resp.status !== 204) {
										return yield* Effect.fail(
											new FatalException({
												orig: new Error(`Label op failed: ${resp.status}`),
											}),
										);
									}
									return resp.data;
								}),
							postSend: () =>
								Effect.gen(function* () {
									for (const { labelId, op } of opsSnapshot) {
										if (op.op === "add") {
											yield* idRepo.bindServerExists("label", labelId);
										}
									}
								}).pipe(
									Effect.mapError((err) => new FatalException({ orig: err })),
								),
						});
					}
					opQueue = { tag: "neither" };
					return events;
				} else if (opQueue.tag === "text") {
					const queuedOps = [...opQueue.queue];
					opQueue = { tag: "neither" };
					const textOpReserveList = (): ReserveList => {
						const reservations: ReserveList = {
							chapterContent: [
								{
									id: chapterContentId,
									kind: "chapterContent",
									desiredState: "updating",
								},
							],
							chapter: [],
							labelGroup: [],
							label: [],
							labelData: [],
						};
						for (const lgId of Effect.runSync(labelDataIndex.getIds())) {
							const slot = Effect.runSync(labelDataIndex.get(lgId));
							reservations.labelData.push({
								id: slot.meta.labelData.labelDataId,
								kind: "labelData",
								desiredState: "idUpdating",
							});
							if (slot.status === "ready" && slot.data) {
								for (const label of slot.data.labels) {
									reservations.label.push({
										id: label.labelId,
										kind: "label",
										desiredState: "updating",
									});
								}
							}
						}
						return reservations;
					};
					const event: RequestEvent = {
						cached: false,
						variant: "textOp",
						active: true,
						retries: 3,
						reservationRequest: {
							reserveList: IdempotentCallable(textOpReserveList),
							skip: () => false,
							wait: () =>
								isAllReserveable(idRepo, textOpReserveList()).pipe(
									Effect.map((ready) => !ready),
								),
						},
						onFailure: () => Effect.succeed(void 0),
						onFatalError: () => Effect.succeed(void 0),
						preSend: () => Effect.succeed(void 0),
						send: () =>
							Effect.gen(function* () {
								const servContentId = yield* idRepo
									.getServerId("chapterContent", chapterContentId)
									.pipe(
										Effect.mapError(
											(err) => new ConnectionException({ orig: err }),
										),
									);
								const servChapterId = yield* idRepo
									.getServerId("chapter", chapterId)
									.pipe(
										Effect.mapError(
											(err) => new ConnectionException({ orig: err }),
										),
									);
								if (!servContentId || !servChapterId) {
									return yield* Effect.fail(
										new FatalException({
											orig: new Error("Missing server IDs for text op"),
										}),
									);
								}
								const resp = yield* Effect.tryPromise(() =>
									updateChapterContentChaptersChapterIdContentPatch(
										servChapterId,
										{
											chapterContentId: servContentId,
											textOps: queuedOps,
										},
									),
								).pipe(
									Effect.mapError(
										(err) => new ConnectionException({ orig: err }),
									),
								);
								if (resp.status !== 200) {
									return yield* Effect.fail(
										new FatalException({
											orig: new Error(`Text op failed: ${resp.status}`),
										}),
									);
								}
								return resp.data;
							}),
						postSend: (data) =>
							Effect.gen(function* () {
								const validated = yield* Schema.decodeUnknown(
									UpdateChapterContentChaptersChapterIdContentPatch200Response,
								)(data).pipe(
									Effect.mapError((err) => new FatalException({ orig: err })),
								);
								yield* idRepo
									.bindServerId(
										"chapterContent",
										chapterContentId,
										ServId(validated.chapterContentId),
									)
									.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
								for (const lgId of yield* labelDataIndex.getIds()) {
									const slot = yield* labelDataIndex.get(lgId);
									const ldId = slot.meta.labelData.labelDataId;
									const oldServId = yield* idRepo
										.getServerId("labelData", ldId)
										.pipe(Effect.catchAll(() => Effect.succeed(null)));
									if (oldServId && validated.labelDataIdMap[oldServId]) {
										yield* idRepo
											.bindServerId(
												"labelData",
												ldId,
												ServId(validated.labelDataIdMap[oldServId]),
											)
											.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
									}
								}
							}).pipe(Effect.mapError((err) => new FatalException({ orig: err }))),
					};
					return [event];
				}
				return [];
			});

		const flush = decorate(_flush);

		const autoFlushIfTagMismatch = (
			incomingTag: "label" | "text" | "neither",
		): Effect.Effect<RequestEvent[], UnknownException> =>
			Effect.gen(function* () {
				if (opQueue.tag !== "neither" && opQueue.tag !== incomingTag) {
					return yield* _flush();
				}
				return [];
			});

		const getReadyLabels = (
			labelGroupId: LGProvId,
			editOnly: boolean = false,
		): Effect.Effect<
			{ labelDataProvId: LDProvId; labels: readonly ProvLabel[] },
			UnknownException
		> =>
			Effect.gen(function* () {
				const slot = yield* labelDataIndex.get(labelGroupId).pipe(
					Effect.mapError(
						() =>
							new UnknownException({
								message: `Label group ${labelGroupId} not found`,
							}),
					),
				);
				if (slot.status !== "ready" || !slot.data) {
					return yield* Effect.fail(
						new UnknownException({
							message: `Labels for group ${labelGroupId} not loaded`,
						}),
					);
				}
				const labelGroupSlot = yield* getters.labelGroup(labelGroupId).pipe(
					Effect.catchAll(() =>
						Effect.fail(
							new UnknownException({
								message: `Label group ${labelGroupId} not found in getters`,
							}),
						),
					),
				);
				if (editOnly && labelGroupSlot.meta.role === "viewer") {
					return yield* Effect.fail(
						new UnknownException({ message: "Viewer role cannot edit labels" }),
					);
				}

				return {
					labelDataProvId: slot.meta.labelData.labelDataId,
					labels: slot.data.labels,
				};
			});

		const _addLabel = (
			labelGroupId: LGProvId,
			startPos: number,
			endPos: number,
			word: string,
			entityGroup?: string,
			score?: number,
			dirty?: boolean,
		): Effect.Effect<RequestEvent[], UnknownException> =>
			Effect.gen(function* () {
				if (destroyed)
					return yield* Effect.fail(
						new UnknownException({ message: "Chapter is destroyed" }),
					);

				const { labelDataProvId, labels } = yield* getReadyLabels(labelGroupId, true);

				if (startPos < 0 || startPos >= endPos || endPos > text.length) {
					return yield* Effect.fail(
						new UnknownException({ message: "Label bounds are out of range" }),
					);
				}
				if (text.slice(startPos, endPos) !== word) {
					return yield* Effect.fail(
						new UnknownException({ message: "Label word must match text" }),
					);
				}
				if (
					labels.some(
						(l) => Math.max(l.labelStart, startPos) < Math.min(l.labelEnd, endPos),
					)
				) {
					return yield* Effect.fail(
						new UnknownException({ message: "Label overlaps with existing label" }),
					);
				}
				if (score != null && (score < 0 || score > 1)) {
					return yield* Effect.fail(
						new UnknownException({ message: "Label score must be between 0 and 1" }),
					);
				}

				const provLabelId = idRepo.newId("label");
				const newLabel: ProvLabel = Prov({
					labelId: provLabelId,
					labelDataId: labelDataProvId,
					labelStart: startPos,
					labelEnd: endPos,
					labelWord: word,
					labelDirty: dirty ?? true,
					labelEntityGroup: entityGroup ?? null,
					labelScore: score ?? 1.0,
				});

				const newLabels = [...labels, newLabel].sort((a, b) => a.labelStart - b.labelStart);
				yield* labelDataIndex
					.setData(labelGroupId, { status: "ready", data: { labels: newLabels } })
					.pipe(
						Effect.mapError(
							() => new UnknownException({ message: "Failed to update label data" }),
						),
					);
				const flushedEvents = yield* autoFlushIfTagMismatch("label");

				if (opQueue.tag === "neither") {
					opQueue = { tag: "label", queue: new Map() };
				}
				if (opQueue.tag === "label") {
					if (!opQueue.queue.has(labelGroupId)) {
						opQueue.queue.set(labelGroupId, []);
					}
					opQueue.queue.get(labelGroupId)!.push({
						labelId: provLabelId,
						op: {
							op: "add",
							startPos,
							endPos,
							word,
							entityGroup: entityGroup ?? null,
							score: score ?? 1.0,
							dirty: dirty ?? true,
						},
					});
				}

				yield* raiseTriggerEvent({
					eventType: "labelChanged",
					op: {
						op: "add",
						startPos,
						endPos,
						word,
						entityGroup: entityGroup ?? null,
						score: score ?? 1.0,
						dirty: dirty ?? true,
						labelGroupId,
						chapterId,
						labelId: provLabelId,
					},
				});
				return flushedEvents;
			});

		const _deleteLabel = (
			labelGroupId: LGProvId,
			startPos: number,
			endPos: number,
		): Effect.Effect<RequestEvent[], UnknownException> =>
			Effect.gen(function* () {
				if (destroyed)
					return yield* Effect.fail(
						new UnknownException({ message: "Chapter is destroyed" }),
					);

				const { labels } = yield* getReadyLabels(labelGroupId, true);

				const labelIndex = labels.findIndex(
					(l) => l.labelStart === startPos && l.labelEnd === endPos,
				);
				if (labelIndex === -1) {
					return yield* Effect.fail(
						new UnknownException({
							message: `Label [${startPos}, ${endPos}) not found`,
						}),
					);
				}
				const label = labels[labelIndex];
				const newLabels = labels.filter((_, idx) => idx !== labelIndex);
				yield* labelDataIndex
					.setData(labelGroupId, { status: "ready", data: { labels: newLabels } })
					.pipe(
						Effect.mapError(
							() => new UnknownException({ message: "Failed to update label data" }),
						),
					);

				const flushedEvents = yield* autoFlushIfTagMismatch("label");

				if (opQueue.tag === "neither") {
					opQueue = { tag: "label", queue: new Map() };
				}
				if (opQueue.tag === "label") {
					if (!opQueue.queue.has(labelGroupId)) {
						opQueue.queue.set(labelGroupId, []);
					}
					opQueue.queue.get(labelGroupId)!.push({
						labelId: label.labelId,
						op: { op: "delete", startPos, endPos, word: label.labelWord },
					});
				}

				yield* raiseTriggerEvent({
					eventType: "labelChanged",
					op: {
						op: "delete",
						startPos,
						endPos,
						word: label.labelWord,
						labelGroupId,
						chapterId,
						labelId: label.labelId,
					},
				});
				return flushedEvents;
			});

		const _updateLabel = (
			labelGroupId: LGProvId,
			startPos: number,
			endPos: number,
			newStartPos?: number | null,
			newEndPos?: number | null,
			newWord?: string | null,
			entityGroup?: string,
			score?: number,
			dirty?: boolean,
		): Effect.Effect<RequestEvent[], UnknownException> =>
			Effect.gen(function* () {
				if (destroyed)
					return yield* Effect.fail(
						new UnknownException({ message: "Chapter is destroyed" }),
					);

				const { labels } = yield* getReadyLabels(labelGroupId, true);

				const labelIndex = labels.findIndex(
					(l) => l.labelStart === startPos && l.labelEnd === endPos,
				);
				if (labelIndex === -1) {
					return yield* Effect.fail(
						new UnknownException({
							message: `Label [${startPos}, ${endPos}) not found`,
						}),
					);
				}
				const currentLabel = labels[labelIndex];
				const nextStart = newStartPos ?? currentLabel.labelStart;
				const nextEnd = newEndPos ?? currentLabel.labelEnd;
				const boundsChanged = newStartPos != null || newEndPos != null;
				if (boundsChanged && newWord == null) {
					return yield* Effect.fail(
						new UnknownException({
							message: "Must provide new word when changing bounds",
						}),
					);
				}
				if (!boundsChanged && newWord != null) {
					return yield* Effect.fail(
						new UnknownException({
							message: "Cannot set new word without changing bounds",
						}),
					);
				}
				const nextWord = newWord ?? currentLabel.labelWord;
				if (nextStart >= nextEnd || nextStart < 0 || nextEnd > text.length) {
					return yield* Effect.fail(
						new UnknownException({ message: "Updated label bounds out of range" }),
					);
				}
				if (text.slice(nextStart, nextEnd) !== nextWord) {
					return yield* Effect.fail(
						new UnknownException({ message: "Updated word must match text" }),
					);
				}

				const overlaps = labels.some((l, idx) => {
					if (idx === labelIndex) return false;
					return Math.max(l.labelStart, nextStart) < Math.min(l.labelEnd, nextEnd);
				});
				if (overlaps) {
					return yield* Effect.fail(
						new UnknownException({
							message: "Updated label overlaps with existing label",
						}),
					);
				}

				const updatedLabel = {
					...currentLabel,
					labelStart: nextStart,
					labelEnd: nextEnd,
					labelWord: nextWord,
					labelEntityGroup: entityGroup ?? currentLabel.labelEntityGroup,
					labelScore: score ?? currentLabel.labelScore,
					labelDirty: dirty ?? currentLabel.labelDirty,
				};
				const newLabels = labels
					.map((l, idx) => (idx === labelIndex ? updatedLabel : l))
					.sort((a, b) => a.labelStart - b.labelStart);
				yield* labelDataIndex
					.setData(labelGroupId, { status: "ready", data: { labels: newLabels } })
					.pipe(
						Effect.mapError(
							() => new UnknownException({ message: "Failed to update label data" }),
						),
					);
				const flushedEvents = yield* autoFlushIfTagMismatch("label");
				if (opQueue.tag === "neither") {
					opQueue = { tag: "label", queue: new Map() };
				}
				if (opQueue.tag === "label") {
					if (!opQueue.queue.has(labelGroupId)) {
						opQueue.queue.set(labelGroupId, []);
					}
					opQueue.queue.get(labelGroupId)!.push({
						labelId: currentLabel.labelId,
						op: {
							op: "update",
							startPos,
							endPos,
							word: currentLabel.labelWord,
							newStartPos: newStartPos ?? undefined,
							newEndPos: newEndPos ?? undefined,
							newWord: newWord ?? undefined,
							entityGroup: entityGroup ?? undefined,
							score: score ?? undefined,
							dirty: dirty ?? undefined,
						},
					});
				}

				yield* raiseTriggerEvent({
					eventType: "labelChanged",
					op: {
						op: "update",
						startPos,
						endPos,
						word: currentLabel.labelWord,
						newStartPos: newStartPos ?? undefined,
						newEndPos: newEndPos ?? undefined,
						newWord: newWord ?? undefined,
						entityGroup: entityGroup ?? undefined,
						score: score ?? undefined,
						dirty: dirty ?? undefined,
						labelGroupId,
						chapterId,
						labelId: currentLabel.labelId,
					},
				});
				return flushedEvents;
			});

		const _insertTextAt = (
			pos: number,
			insertedText: string,
		): Effect.Effect<RequestEvent[], UnknownException> =>
			Effect.gen(function* () {
				if (destroyed)
					return yield* Effect.fail(
						new UnknownException({ message: "Chapter is destroyed" }),
					);

				const role = yield* getters.role();
				if (role === "viewer") {
					return yield* Effect.fail(
						new UnknownException({ message: "Viewer role cannot edit text" }),
					);
				}

				if (pos < 0 || pos > text.length) {
					return yield* Effect.fail(
						new UnknownException({ message: "Insert position out of bounds" }),
					);
				}
				const flushedEvents = yield* autoFlushIfTagMismatch("text");
				if (insertedText.length === 0) return flushedEvents;

				const delta = insertedText.length;
				const insertIds = yield* labelDataIndex
					.getIds()
					.pipe(Effect.catchAll(() => Effect.succeed([] as LGProvId[])));
				for (const ldId of insertIds) {
					const slot = yield* labelDataIndex
						.get(ldId)
						.pipe(Effect.catchAll(() => Effect.succeed(null)));
					if (!slot || slot.status !== "ready" || !slot.data) continue;
					const newLabels = slot.data.labels
						.filter((l) => l.labelEnd <= pos || l.labelStart >= pos)
						.map((l) => {
							if (l.labelStart >= pos) {
								return {
									...l,
									labelStart: l.labelStart + delta,
									labelEnd: l.labelEnd + delta,
								};
							}
							return l;
						})
						.sort((a, b) => a.labelStart - b.labelStart);
					yield* labelDataIndex
						.setData(ldId, { status: "ready", data: { labels: newLabels } })
						.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
				}

				text = text.slice(0, pos) + insertedText + text.slice(pos);

				if (opQueue.tag === "neither") {
					opQueue = { tag: "text", queue: [] };
				}
				if (opQueue.tag === "text") {
					opQueue.queue.push({ op: "insert", start: pos, text: insertedText });
				}

				yield* raiseTriggerEvent({
					eventType: "textChanged",
					op: { op: "insert", start: pos, text: insertedText },
					chapterId,
				});
				return flushedEvents;
			});

		const _deleteTextAt = (
			startPos: number,
			endPos: number,
		): Effect.Effect<RequestEvent[], UnknownException> =>
			Effect.gen(function* () {
				if (destroyed)
					return yield* Effect.fail(
						new UnknownException({ message: "Chapter is destroyed" }),
					);

				const role = yield* getters.role();
				if (role === "viewer") {
					return yield* Effect.fail(
						new UnknownException({ message: "Viewer role cannot edit text" }),
					);
				}

				if (startPos < 0 || endPos > text.length || startPos >= endPos) {
					return yield* Effect.fail(
						new UnknownException({ message: "Delete range out of bounds" }),
					);
				}
				const deletedText = text.slice(startPos, endPos);
				const flushedEvents = yield* autoFlushIfTagMismatch("text");
				if (deletedText.length === 0) return flushedEvents;

				const delta = deletedText.length;
				const deleteIds = yield* labelDataIndex
					.getIds()
					.pipe(Effect.catchAll(() => Effect.succeed([] as LGProvId[])));
				for (const ldId of deleteIds) {
					const slot = yield* labelDataIndex
						.get(ldId)
						.pipe(Effect.catchAll(() => Effect.succeed(null)));
					if (!slot || slot.status !== "ready" || !slot.data) continue;
					const newLabels = slot.data.labels
						.filter((l) => l.labelEnd <= startPos || l.labelStart >= endPos)
						.map((l) => {
							if (l.labelStart >= endPos) {
								return {
									...l,
									labelStart: l.labelStart - delta,
									labelEnd: l.labelEnd - delta,
								};
							}
							return l;
						})
						.sort((a, b) => a.labelStart - b.labelStart);
					yield* labelDataIndex
						.setData(ldId, { status: "ready", data: { labels: newLabels } })
						.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
				}

				text = text.slice(0, startPos) + text.slice(endPos);

				if (opQueue.tag === "neither") {
					opQueue = { tag: "text", queue: [] };
				}
				if (opQueue.tag === "text") {
					opQueue.queue.push({ op: "delete", start: startPos, text: deletedText });
				}

				yield* raiseTriggerEvent({
					eventType: "textChanged",
					op: { op: "delete", start: startPos, text: deletedText },
					chapterId,
				});
				return flushedEvents;
			});

		const _reloadGroup = (
			labelGroupId: LGProvId,
		): Effect.Effect<RequestEvent[], UnknownException> =>
			Effect.gen(function* () {
				if (destroyed)
					return yield* Effect.fail(
						new UnknownException({ message: "Chapter is destroyed" }),
					);
				// Check if label group still exists in getters. If not, delete from index and raise event.
				const labelGroupSlotEither = yield* Effect.either(getters.labelGroup(labelGroupId));
				if (labelGroupSlotEither._tag === "Left") {
					const slot = yield* Effect.either(labelDataIndex.get(labelGroupId));
					if (slot._tag === "Right") {
						yield* labelDataIndex
							.delete(labelGroupId)
							.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
					}
					yield* raiseTriggerEvent({
						eventType: "labelDataLoaded",
						chapterId,
						labelGroupId,
						wasDeleted: true,
					});
					return [];
				}
				// label group exists, proceed with reload
				const slotEither = yield* Effect.either(labelDataIndex.get(labelGroupId));
				if (slotEither._tag === "Left") {
					yield* labelDataIndex
						.new(labelGroupId, {
							labelData: Prov({
								labelDataId: idRepo.newId("labelData"),
								chapterContentId,
								labelGroupId,
							}),
						})
						.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
				}
				const slot =
					slotEither._tag === "Right"
						? slotEither.right
						: yield* labelDataIndex
								.get(labelGroupId)
								.pipe(
									Effect.mapError((err) => new UnknownException({ orig: err })),
								);
				if (slot.status === "loading") return [];
				yield* raiseTriggerEvent({
					eventType: "labelDataReloading",
					chapterId,
					labelGroupId,
				});
				yield* labelDataIndex
					.setData(labelGroupId, { status: "loading" })
					.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
				yield* labelDataIndex
					.increment(labelGroupId)
					.pipe(Effect.catchAll(() => Effect.succeed(void 0)));

				const oldLabelDataProvId = slot.meta.labelData.labelDataId;
				const oldLabelIds: LProvId[] =
					slot.status === "ready" && slot.data
						? slot.data.labels.map((l) => l.labelId)
						: [];
				const newLabelDataProvId = idRepo.newId("labelData");

				const onError = () =>
					Effect.gen(function* () {
						yield* labelDataIndex
							.setData(labelGroupId, { status: "error" })
							.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
						yield* labelDataIndex
							.decrement(labelGroupId)
							.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
					});

				const reloadReserveList: () => ReserveList = () => {
					const curLabelDataState = Effect.runSyncExit(
						idRepo.idObjState("labelData", oldLabelDataProvId),
					);
					if (curLabelDataState._tag === "Failure") {
						return {
							chapter: [],
							chapterContent: [],
							labelGroup: [
								{ id: labelGroupId, kind: "labelGroup", desiredState: "locked" },
							],
							labelData: [],
							label: oldLabelIds.map((id) => ({
								id,
								kind: "label" as const,
								desiredState: "detaching" as const,
							})),
						};
					}
					const curState = curLabelDataState.value;
					let desiredState: "detaching" | "killing";
					if (curState === "pending") {
						desiredState = "killing";
					} else {
						desiredState = "detaching";
					}
					return {
						chapter: [],
						chapterContent: [],
						labelGroup: [
							{ id: labelGroupId, kind: "labelGroup", desiredState: "locked" },
						],
						labelData: [
							{
								id: oldLabelDataProvId,
								kind: "labelData",
								desiredState: desiredState,
							},
						],
						label: oldLabelIds.map((id) => ({
							id,
							kind: "label" as const,
							desiredState: "detaching" as const,
						})),
					};
				};

				const event: RequestEvent = {
					cached: false,
					variant: "reloadGroup",
					active: false,
					retries: 3,
					reservationRequest: {
						reserveList: IdempotentCallable(reloadReserveList),
						skip: () => false,
						wait: () =>
							isAllReserveable(idRepo, reloadReserveList()).pipe(
								Effect.map((ready) => !ready),
							),
					},
					onFailure: onError,
					onFatalError: onError,
					preSend: () => Effect.succeed(void 0),
					send: () =>
						Effect.gen(function* () {
							const servChapterId = yield* idRepo
								.getServerId("chapter", chapterId)
								.pipe(Effect.mapError((err) => new FatalException({ orig: err })));
							const servLabelGroupId = yield* idRepo
								.getServerId("labelGroup", labelGroupId)
								.pipe(Effect.mapError((err) => new FatalException({ orig: err })));
							if (!servChapterId || !servLabelGroupId) {
								return yield* Effect.fail(
									new FatalException({
										orig: new Error("Missing server IDs for reload group"),
									}),
								);
							}
							const resp = yield* Effect.tryPromise(() =>
								readEditChapterLabelDataEditChapterDataChapterIdLabelDataGet(
									servChapterId,
									{
										labelGroupIds: [servLabelGroupId],
									},
								),
							).pipe(
								Effect.mapError((err) => new ConnectionException({ orig: err })),
							);
							if (resp.status !== 200) {
								return yield* Effect.fail(
									new FatalException({
										orig: new Error(`Reload failed: ${resp.status}`),
									}),
								);
							}
							return resp.data;
						}),
					postSend: (data: unknown) =>
						Effect.gen(function* () {
							const validated = yield* Schema.decodeUnknown(
								ReadEditChapterLabelDataEditChapterDataChapterIdLabelDataGet200Response,
							)(data).pipe(
								Effect.mapError((err) => new FatalException({ orig: err })),
							);
							const entry = validated[0];
							if (!entry) {
								return yield* Effect.fail(
									new FatalException({
										orig: new Error("Reload returned no data for label group"),
									}),
								);
							}
							yield* idRepo
								.bindServerId(
									"labelData",
									newLabelDataProvId,
									ServId(entry.labelData.labelDataId),
								)
								.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
							const provLabels: ProvLabel[] = entry.labels
								.map((l) => {
									const provLabelId = idRepo.newIdAndBindExists("label");
									return Prov({
										...l,
										labelId: provLabelId,
										labelDataId: newLabelDataProvId,
									});
								})
								.sort((a, b) => a.labelStart - b.labelStart);
							yield* labelDataIndex
								.setMeta(labelGroupId, {
									labelData: Prov({
										labelDataId: newLabelDataProvId,
										chapterContentId,
										labelGroupId,
									}),
								})
								.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
							yield* labelDataIndex
								.setData(labelGroupId, {
									status: "ready",
									data: { labels: provLabels },
								})
								.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
							yield* labelDataIndex
								.decrement(labelGroupId)
								.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
							yield* raiseTriggerEvent({
								eventType: "labelDataLoaded",
								labelGroupId,
								chapterId,
								wasDeleted: false,
							});
						}).pipe(Effect.mapError((err) => new FatalException({ orig: err }))),
				};
				const flushedOps = yield* autoFlushIfTagMismatch("neither");
				return [...flushedOps, event];
			});

		const addLabel = decorate(_addLabel);
		const deleteLabel = decorate(_deleteLabel);
		const updateLabel = decorate(_updateLabel);
		const insertTextAt = decorate(_insertTextAt);
		const deleteTextAt = decorate(_deleteTextAt);
		const reloadGroup = (labelGroupId: LGProvId, now: boolean) =>
			Effect.gen(function* () {
				const requestEvents = yield* decorate(_reloadGroup)(labelGroupId);
				if (now) {
					const dispatchedEvents = yield* dispatcherFlush();
					requestEvents.push(...dispatchedEvents);
				}
				return requestEvents;
			});

		const destroy = (): Effect.Effect<RequestEvent[]> => {
			destroyed = true;
			return Effect.succeed([]);
		};

		return {
			addLabel,
			deleteLabel,
			updateLabel,
			insertTextAt,
			deleteTextAt,
			flush,
			reloadGroup,
			destroy,
			getters: {
				labelDataSlot: (labelGroupId: LGProvId) => labelDataIndex.get(labelGroupId),
				text: () => Effect.succeed(text),
			},
		};
	});
