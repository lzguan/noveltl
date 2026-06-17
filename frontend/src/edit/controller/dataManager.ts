import { Effect, Schema } from "effect";
import {
	buildChapterIndex,
	buildLabelDataIndex,
	buildLabelGroupIndex,
	buildRequestQueueDispatcher,
	type ChapterIndex,
	type LabelGroupIndex,
	type LabelGroupSlot,
} from "./dmHelpers";
import {
	AlreadyOpenException,
	ConnectionException,
	FatalException,
	LoadingException,
	NotFoundException,
} from "./types/errors";
import { TimeoutException, UnknownException } from "effect/Cause";
import type { TriggerEvent } from "./types/controllerTypes";
import {
	CProvId,
	type IDRepository,
	type InFlightIdStatus,
	type Kind,
	LGProvId,
	LProvId,
	type ProvChapter,
	type ProvLabel,
	type ProvLabelGroup,
	ServId,
} from "./types/idTypes";
import { IdempotentCallable, makeReservationRequest, Prov } from "./types/helperTypes";
import type { Chapter, LabelGroup, LabelRole, Novel, TextOp } from "@/api/models";
import type { RequestEvent, ReserveList } from "./types/requestTypes";
import type { LabelOp } from "./types/dataTypes";
import {
	CreateChapterNovelsNovelIdChaptersPost200Response,
	CreateLabelGroupLabelGroupsPost200Response,
	ReadEditChapterDataEditChapterDataChapterIdGet200Response,
	UpdateChapterContentChaptersChapterIdContentPatch200Response,
} from "@/api/endpoints/default/default.effect";
import {
	createChapterNovelsNovelIdChaptersPost,
	createLabelGroupLabelGroupsPost,
	readEditChapterDataEditChapterDataChapterIdGet,
	readLabelsByLabelDataLabelDatasLabelDataIdLabelsGet,
	updateChapterContentChaptersChapterIdContentPatch,
	updateLabelDataStreamLabelDatasLabelDataIdPatch,
} from "@/api/endpoints/default/default";
import type { Role } from "@/api/models/role";
import type { ChapterDataManager, NovelDataManager } from "./types/dataTypes";

type NovelData = {
	novel: Novel;
	chapters: Chapter[];
	labelGroups: { labelGroup: LabelGroup; role: LabelRole }[];
	novelRole: Role;
};

export const buildNovelDataManager = (
	fetchNovelData: () => Effect.Effect<NovelData, ConnectionException | TimeoutException>,
	raiseTriggerEvent: (event: TriggerEvent) => void,
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
					const newId = idRepo.newIdAndBindId("labelGroup", ServId(val.labelGroup.labelGroupId));
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
							() => new UnknownException({ message: "Failed to add label group to index" }),
						),
					);
				yield* labelGroupsIndex
					.increment(newId)
					.pipe(
						Effect.mapError(
							() => new UnknownException({ message: "Failed to increment label group index" }),
						),
					);
				raiseTriggerEvent({ eventType: "labelGroupAdded", labelGroup: newLabelGroup });
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
											orig: new Error(`Failed to create label group: ${resp}`),
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
								yield* idRepo.bindServerId("labelGroup", newId, ServId(validated.labelGroupId));
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
		): Effect.Effect<RequestEvent[], UnknownException> =>
			Effect.gen(function* () {
				const newId = idRepo.newId("chapter");
				const newChapter: ProvChapter = Prov({
					chapterId: newId,
					chapterNum,
					chapterTitle,
					chapterIsPublic,
					novelId: novelData.novel.novelId,
				});
				yield* chaptersIndex
					.new(newId, { chapter: newChapter })
					.pipe(
						Effect.mapError(
							() => new UnknownException({ message: "Failed to add chapter to index" }),
						),
					);
				yield* chaptersIndex
					.increment(newId)
					.pipe(
						Effect.mapError(
							() => new UnknownException({ message: "Failed to increment chapter index" }),
						),
					);
				raiseTriggerEvent({ eventType: "chapterAdded", chapter: newChapter });
				const onError = (): Effect.Effect<void> => {
					return chaptersIndex.decrement(newId).pipe(Effect.catchAll(() => Effect.succeed(void 0)));
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
									createChapterNovelsNovelIdChaptersPost(novelData.novel.novelId, {
										chapterNum,
										chapterTitle,
										chapterIsPublic,
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
								yield* idRepo.bindServerId("chapter", newId, ServId(validated.metadata.chapterId));
								yield* chaptersIndex.decrement(newId);
							}).pipe(Effect.mapError((err) => new FatalException({ orig: err }))),
					},
				];
			});
		const addChapter = decorate(_addChapter);

		const _openChapter = (
			chapterId: CProvId,
			eager: LGProvId[],
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
									.pipe(Effect.mapError((err) => new FatalException({ orig: err })));
								const esi = yield* Effect.all(
									eager.map((id) => idRepo.getServerId("labelGroup", id)),
								).pipe(Effect.mapError((err) => new FatalException({ orig: err })));
								const eagerServIds = esi.filter((id) => id !== null);
								if (chapterServId === null) {
									return yield* Effect.fail(
										new FatalException({
											orig: new Error(`Unexpected: chapter ${chapterId} does not have a server id`),
										}),
									);
								}
								const resp = yield* Effect.tryPromise(async () => {
									const inResp = await readEditChapterDataEditChapterDataChapterIdGet(
										chapterServId,
										{
											eager: eagerServIds,
										},
									);
									return inResp;
								}).pipe(Effect.mapError((err) => new ConnectionException({ orig: err })));
								if (resp.status !== 200) {
									return yield* Effect.fail(
										new FatalException({
											orig: new Error(`Failed to read chapter data: ${resp.status}`),
										}),
									);
								}
								return resp.data;
							}),
						postSend: (resp: unknown) =>
							Effect.gen(function* () {
								const validated = yield* Schema.validate(
									ReadEditChapterDataEditChapterDataChapterIdGet200Response,
								)(resp).pipe(Effect.mapError((err) => new FatalException({ orig: err })));
								const chapterDataManager = yield* buildChapterDataManager(
									validated,
									chapterId,
									raiseTriggerEvent,
									idRepo,
									{
										labelGroupIds: () => labelGroupsIndex.getIds(),
										labelGroup: (labelGroupId) => labelGroupsIndex.get(labelGroupId),
									},
								).pipe(Effect.mapError((err) => new FatalException({ orig: err })));
								yield* chaptersIndex
									.setData(chapterId, {
										status: "ready",
										data: {
											chapterData: chapterDataManager,
										},
									})
									.pipe(Effect.mapError((err) => new FatalException({ orig: err })));
								raiseTriggerEvent({
									eventType: "chapterOpened",
									chapterId,
								});
							}),
					},
				];
			});
		const openChapter = (chapterId: CProvId, eager: LGProvId[], now: boolean) =>
			Effect.gen(function* () {
				const reqEvents = yield* decorate(_openChapter)(chapterId, eager);
				if (now) {
					const flushEvents = yield* flush();
					reqEvents.push(...flushEvents);
				}
				return reqEvents;
			});
		const getters = {};

		return {
			addLabelGroup,
			addChapter,
			openChapter,
			flush,
			getters,
		};
	});

export const buildChapterDataManager = (
	editChapterData: typeof ReadEditChapterDataEditChapterDataChapterIdGet200Response.Type,
	chapterId: CProvId,
	raiseTriggerEvent: (event: TriggerEvent) => void,
	idRepo: IDRepository,
	getters: {
		labelGroupIds: () => Effect.Effect<LGProvId[], UnknownException>;
		labelGroup: (labelGroupId: LGProvId) => Effect.Effect<LabelGroupSlot, NotFoundException>;
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
			const provLdId = idRepo.newIdAndBindId("labelData", ServId(entry.labelData.labelDataId));
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
			const provLdId = idRepo.newIdAndBindId("labelData", ServId(entry.labelData.labelDataId));
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

		// Op queue: keyed by labelGroupProvId for label ops.
		// Only one tag can be active at a time. Tag switching is handled by auto-flush in actions.
		let opQueue:
			| { tag: "label"; queue: Map<LGProvId, { labelId: LProvId; op: LabelOp }[]> }
			| { tag: "text"; queue: TextOp[] }
			| { tag: "neither" } = { tag: "neither" };

		let destroyed = false;

		const { decorate, flush: _dispatcherFlush } = buildRequestQueueDispatcher<RequestEvent>();

		const buildLabelReservations = (
			ops: { labelId: LProvId; op: LabelOp }[],
		): { id: LProvId; kind: "label"; desiredState: InFlightIdStatus }[] => {
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
						const slot = yield* labelDataIndex
							.get(labelGroupProvId)
							.pipe(
								Effect.mapError(
									() => new UnknownException({ message: "Label group not found in index" }),
								),
							);
						const labelDataProvId = slot.meta.labelData.labelDataId;
						const opsSnapshot = [...ops];
						events.push({
							cached: false,
							variant: "labelOp",
							active: false,
							retries: 3,
							reservationRequest: {
								reserveList: IdempotentCallable(() => ({
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
								})),
								skip: () => false,
								wait: () =>
									Effect.gen(function* () {
										const a = yield* idRepo.isReserveable("labelData", labelDataProvId, "updating");
										const b = yield* idRepo.isReserveable(
											"chapterContent",
											chapterContentId,
											"locked",
										);
										return !a || !b;
									}),
							},
							onFailure: () => Effect.succeed(void 0),
							onFatalError: () => Effect.succeed(void 0),
							preSend: () => Effect.succeed(void 0),
							send: () =>
								Effect.gen(function* () {
									const servLdId = yield* idRepo
										.getServerId("labelData", labelDataProvId)
										.pipe(Effect.mapError((err) => new FatalException({ orig: err })));
									if (!servLdId) {
										return yield* Effect.fail(
											new FatalException({ orig: new Error("Label data has no server ID") }),
										);
									}
									const resp = yield* Effect.tryPromise(() =>
										updateLabelDataStreamLabelDatasLabelDataIdPatch(servLdId, {
											ops: opsSnapshot.map(({ op }) => op),
										}),
									).pipe(Effect.mapError((err) => new ConnectionException({ orig: err })));
									if (resp.status !== 204) {
										return yield* Effect.fail(
											new FatalException({ orig: new Error(`Label op failed: ${resp.status}`) }),
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
								}).pipe(Effect.mapError((err) => new FatalException({ orig: err }))),
						});
					}
					opQueue = { tag: "neither" };
					return events;
				} else if (opQueue.tag === "text") {
					const queuedOps = [...opQueue.queue];
					opQueue = { tag: "neither" };
					const event: RequestEvent = {
						cached: false,
						variant: "textOp",
						active: false,
						retries: 3,
						reservationRequest: {
							reserveList: IdempotentCallable(() => {
								const reservations: ReserveList = {
									chapterContent: [
										{ id: chapterContentId, kind: "chapterContent", desiredState: "updating" },
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
							}),
							skip: () => false,
							wait: () =>
								Effect.gen(function* () {
									// needs to ensure label datas and labels are reserveable as well.
									const isReserveable = yield* idRepo.isReserveable(
										"chapterContent",
										chapterContentId,
										"updating",
									);
									return !isReserveable;
								}),
						},
						onFailure: () => Effect.succeed(void 0),
						onFatalError: () => Effect.succeed(void 0),
						preSend: () => Effect.succeed(void 0),
						send: () =>
							Effect.gen(function* () {
								const servContentId = yield* idRepo
									.getServerId("chapterContent", chapterContentId)
									.pipe(Effect.mapError((err) => new ConnectionException({ orig: err })));
								const servChapterId = yield* idRepo
									.getServerId("chapter", chapterId)
									.pipe(Effect.mapError((err) => new ConnectionException({ orig: err })));
								if (!servContentId || !servChapterId) {
									return yield* Effect.fail(
										new FatalException({ orig: new Error("Missing server IDs for text op") }),
									);
								}
								const resp = yield* Effect.tryPromise(() =>
									updateChapterContentChaptersChapterIdContentPatch(servChapterId, {
										chapterContentId: servContentId,
										textOps: queuedOps,
									}),
								).pipe(Effect.mapError((err) => new ConnectionException({ orig: err })));
								if (resp.status !== 200) {
									return yield* Effect.fail(
										new FatalException({ orig: new Error(`Text op failed: ${resp.status}`) }),
									);
								}
								return resp.data;
							}),
						postSend: (data) =>
							Effect.gen(function* () {
								const validated = yield* Schema.decodeUnknown(
									UpdateChapterContentChaptersChapterIdContentPatch200Response,
								)(data).pipe(Effect.mapError((err) => new FatalException({ orig: err })));
								yield* idRepo
									.bindServerId(
										"chapterContent",
										chapterContentId,
										ServId(validated.chapterContentId),
									)
									.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
								for (const [ldId] of labelDataIndex.index) {
									const oldServId = yield* idRepo
										.getServerId("labelData", ldId)
										.pipe(Effect.catchAll(() => Effect.succeed(null)));
									if (oldServId && validated.labelDataIdMap[oldServId]) {
										yield* idRepo
											.bindServerId("labelData", ldId, ServId(validated.labelDataIdMap[oldServId]))
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

		const autoFlushIfTagMismatch = (incomingTag: "label" | "text"): Effect.Effect<RequestEvent[]> =>
			Effect.gen(function* () {
				if (opQueue.tag !== "neither" && opQueue.tag !== incomingTag) {
					return yield* _flush();
				}
				return [];
			});

		const getReadyLabels = (
			labelGroupId: ProvId,
		): Effect.Effect<
			{
				slot: typeof labelDataIndex extends { get: (id: ProvId) => Effect.Effect<infer S, any> }
					? S
					: never;
				labels: readonly ProvLabel[];
			},
			UnknownException
		> =>
			Effect.gen(function* () {
				const slot = yield* labelDataIndex
					.get(labelGroupId)
					.pipe(
						Effect.mapError(
							() => new UnknownException({ message: `Label group ${labelGroupId} not found` }),
						),
					);
				if (slot.status !== "ready" || !slot.data) {
					return yield* Effect.fail(
						new UnknownException({ message: `Labels for group ${labelGroupId} not loaded` }),
					);
				}
				return { slot, labels: slot.data.labels };
			});

		const addLabel = (
			labelGroupId: ProvId,
			startPos: number,
			endPos: number,
			word: string,
			entityGroup?: string,
			score?: number,
			dirty?: boolean,
		): Effect.Effect<RequestEvent[], UnknownException> =>
			Effect.gen(function* () {
				if (destroyed)
					return yield* Effect.fail(new UnknownException({ message: "Chapter is destroyed" }));
				const flushedEvents = yield* autoFlushIfTagMismatch("label");
				const { labels } = yield* getReadyLabels(labelGroupId);

				if (startPos < 0 || startPos >= endPos || endPos > text.length) {
					return yield* Effect.fail(
						new UnknownException({ message: "Label bounds are out of range" }),
					);
				}
				if (word.length !== endPos - startPos) {
					return yield* Effect.fail(
						new UnknownException({ message: "Label word length must match bounds" }),
					);
				}
				if (text.slice(startPos, endPos) !== word) {
					return yield* Effect.fail(
						new UnknownException({ message: "Label word must match text" }),
					);
				}
				if (labels.some((l) => Math.max(l.labelStart, startPos) < Math.min(l.labelEnd, endPos))) {
					return yield* Effect.fail(
						new UnknownException({ message: "Label overlaps with existing label" }),
					);
				}

				const provLabelId = idRepo.newId("label");
				const newLabel = Prov({
					labelId: provLabelId,
					labelDataId: labelGroupId,
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
						Effect.mapError(() => new UnknownException({ message: "Failed to update label data" })),
					);

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

				raiseTriggerEvent({
					eventType: "labelChanged",
					op: {
						op: "add",
						startPos,
						endPos,
						word,
						entityGroup: entityGroup ?? null,
						score: score ?? 1.0,
						dirty: dirty ?? true,
					},
					labelGroupId,
					chapterId,
				});
				return flushedEvents;
			});

		const deleteLabel = (
			labelGroupId: ProvId,
			startPos: number,
			endPos: number,
		): Effect.Effect<RequestEvent[], UnknownException> =>
			Effect.gen(function* () {
				if (destroyed)
					return yield* Effect.fail(new UnknownException({ message: "Chapter is destroyed" }));
				const flushedEvents = yield* autoFlushIfTagMismatch("label");
				const { labels } = yield* getReadyLabels(labelGroupId);

				const labelIndex = labels.findIndex(
					(l) => l.labelStart === startPos && l.labelEnd === endPos,
				);
				if (labelIndex === -1) {
					return yield* Effect.fail(
						new UnknownException({ message: `Label [${startPos}, ${endPos}) not found` }),
					);
				}
				const label = labels[labelIndex];
				const newLabels = labels.filter((_, idx) => idx !== labelIndex);
				yield* labelDataIndex
					.setData(labelGroupId, { status: "ready", data: { labels: newLabels } })
					.pipe(
						Effect.mapError(() => new UnknownException({ message: "Failed to update label data" })),
					);

				if (opQueue.tag === "neither") {
					opQueue = { tag: "label", queue: new Map() };
				}
				if (opQueue.tag === "label") {
					if (!opQueue.queue.has(labelGroupId)) {
						opQueue.queue.set(labelGroupId, []);
					}
					opQueue.queue.get(labelGroupId)!.push({
						labelId: ProvId(label.labelId),
						op: { op: "delete", startPos, endPos, word: label.labelWord },
					});
				}

				raiseTriggerEvent({
					eventType: "labelChanged",
					op: { op: "delete", startPos, endPos, word: label.labelWord },
					labelGroupId,
					chapterId,
				});
				return flushedEvents;
			});

		const updateLabel = (
			labelGroupId: ProvId,
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
					return yield* Effect.fail(new UnknownException({ message: "Chapter is destroyed" }));
				const flushedEvents = yield* autoFlushIfTagMismatch("label");
				const { labels } = yield* getReadyLabels(labelGroupId);

				const labelIndex = labels.findIndex(
					(l) => l.labelStart === startPos && l.labelEnd === endPos,
				);
				if (labelIndex === -1) {
					return yield* Effect.fail(
						new UnknownException({ message: `Label [${startPos}, ${endPos}) not found` }),
					);
				}
				const currentLabel = labels[labelIndex];
				const nextStart = newStartPos ?? currentLabel.labelStart;
				const nextEnd = newEndPos ?? currentLabel.labelEnd;
				const boundsChanged = newStartPos != null || newEndPos != null;
				if (boundsChanged && newWord == null) {
					return yield* Effect.fail(
						new UnknownException({ message: "Must provide new word when changing bounds" }),
					);
				}
				if (!boundsChanged && newWord != null) {
					return yield* Effect.fail(
						new UnknownException({ message: "Cannot set new word without changing bounds" }),
					);
				}
				const nextWord = newWord ?? currentLabel.labelWord;
				if (nextStart >= nextEnd || nextStart < 0 || nextEnd > text.length) {
					return yield* Effect.fail(
						new UnknownException({ message: "Updated label bounds out of range" }),
					);
				}
				if (nextWord.length !== nextEnd - nextStart) {
					return yield* Effect.fail(
						new UnknownException({ message: "Updated word length must match bounds" }),
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
						new UnknownException({ message: "Updated label overlaps with existing label" }),
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
						Effect.mapError(() => new UnknownException({ message: "Failed to update label data" })),
					);

				if (opQueue.tag === "neither") {
					opQueue = { tag: "label", queue: new Map() };
				}
				if (opQueue.tag === "label") {
					if (!opQueue.queue.has(labelGroupId)) {
						opQueue.queue.set(labelGroupId, []);
					}
					opQueue.queue.get(labelGroupId)!.push({
						labelId: ProvId(currentLabel.labelId),
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

				raiseTriggerEvent({
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
					},
					labelGroupId,
					chapterId,
				});
				return flushedEvents;
			});

		const insertTextAt = (
			pos: number,
			insertedText: string,
		): Effect.Effect<RequestEvent[], UnknownException> =>
			Effect.gen(function* () {
				if (destroyed)
					return yield* Effect.fail(new UnknownException({ message: "Chapter is destroyed" }));
				const flushedEvents = yield* autoFlushIfTagMismatch("text");

				if (pos < 0 || pos > text.length) {
					return yield* Effect.fail(
						new UnknownException({ message: "Insert position out of bounds" }),
					);
				}
				if (insertedText.length === 0) return flushedEvents;

				const delta = insertedText.length;
				for (const [ldId, slot] of labelDataIndex.index) {
					if (slot.status !== "ready" || !slot.data) continue;
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

				raiseTriggerEvent({
					eventType: "textChanged",
					op: { op: "insert", start: pos, text: insertedText },
					chapterId,
				});
				return flushedEvents;
			});

		const deleteTextAt = (
			startPos: number,
			endPos: number,
		): Effect.Effect<RequestEvent[], UnknownException> =>
			Effect.gen(function* () {
				if (destroyed)
					return yield* Effect.fail(new UnknownException({ message: "Chapter is destroyed" }));
				const flushedEvents = yield* autoFlushIfTagMismatch("text");

				if (startPos < 0 || endPos > text.length || startPos >= endPos) {
					return yield* Effect.fail(
						new UnknownException({ message: "Delete range out of bounds" }),
					);
				}
				const deletedText = text.slice(startPos, endPos);
				if (deletedText.length === 0) return flushedEvents;

				const delta = deletedText.length;
				for (const [ldId, slot] of labelDataIndex.index) {
					if (slot.status !== "ready" || !slot.data) continue;
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

				raiseTriggerEvent({
					eventType: "textChanged",
					op: { op: "delete", start: startPos, text: deletedText },
					chapterId,
				});
				return flushedEvents;
			});

		const _reloadGroup = (labelGroupId: ProvId): Effect.Effect<RequestEvent[]> =>
			Effect.gen(function* () {
				const slot = yield* labelDataIndex
					.get(labelGroupId)
					.pipe(
						Effect.mapError(
							() =>
								new FatalException({ orig: new Error(`Label group ${labelGroupId} not found`) }),
						),
					);
				if (slot.status === "loading") return [];
				yield* labelDataIndex
					.setData(labelGroupId, { status: "loading" })
					.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
				yield* labelDataIndex
					.increment(labelGroupId)
					.pipe(Effect.catchAll(() => Effect.succeed(void 0)));

				const oldLabelDataProvId = slot.meta.labelData.labelDataId;
				const oldLabelIds =
					slot.status === "ready" && slot.data
						? slot.data.labels.map((l) => ProvId(l.labelId))
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

				return [
					{
						cached: false,
						variant: "reloadGroup",
						active: true,
						retries: 3,
						reservationRequest: {
							reserveList: IdempotentCallable(() => {
								const reservations: { id: ProvId; kind: Kind; desiredState: InFlightIdStatus }[] = [
									{ id: newLabelDataProvId, kind: "labelData", desiredState: "loading" },
									{ id: labelGroupId, kind: "labelGroup", desiredState: "locked" },
								];
								for (const labelId of oldLabelIds) {
									reservations.push({ id: labelId, kind: "label", desiredState: "detaching" });
								}
								return reservations;
							}),
							skip: () => false,
							wait: () =>
								oldLabelIds.some(
									(id) =>
										!Effect.runSync(
											idRepo
												.isReserveable("label", id, "detaching")
												.pipe(Effect.catchAll(() => Effect.succeed(false))),
										),
								),
						},
						onFailure: onError,
						onFatalError: onError,
						preSend: () => Effect.succeed(void 0),
						send: () =>
							Effect.gen(function* () {
								const servLdId = yield* idRepo
									.getServerId("labelData", oldLabelDataProvId)
									.pipe(Effect.mapError((err) => new ConnectionException({ orig: err })));
								if (!servLdId) {
									return yield* Effect.fail(
										new FatalException({ orig: new Error("No server ID for label data") }),
									);
								}
								const resp = yield* Effect.tryPromise(() =>
									readLabelsByLabelDataLabelDatasLabelDataIdLabelsGet(servLdId),
								).pipe(Effect.mapError((err) => new ConnectionException({ orig: err })));
								if (resp.status !== 200) {
									return yield* Effect.fail(
										new FatalException({ orig: new Error(`Reload failed: ${resp.status}`) }),
									);
								}
								return resp.data;
							}),
						postSend: (data: unknown) =>
							Effect.gen(function* () {
								const labels = data;
								const provLabels: ProvLabel[] = labels
									.map((l) => {
										const provLabelId = idRepo.newIdAndBindExists("label");
										return Prov({
											...l,
											labelId: provLabelId,
											labelDataId: labelGroupId,
										});
									})
									.sort((a, b) => a.labelStart - b.labelStart);
								yield* labelDataIndex
									.setData(labelGroupId, { status: "ready", data: { labels: provLabels } })
									.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
								yield* labelDataIndex
									.decrement(labelGroupId)
									.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
							}).pipe(Effect.mapError((err) => new FatalException({ orig: err }))),
					},
				];
			});

		const reloadGroup = decorate(_reloadGroup);

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
			getters: {},
		};
	});
