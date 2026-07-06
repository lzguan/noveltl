import { Effect, Schema } from "effect";
import {
	buildAutoLabelIndex,
	buildAutoLabelRunIndex,
	buildRequestQueueDispatcher,
} from "./dmHelpers";
import {
	CacheConflictException,
	ConnectionException,
	FatalException,
	NotFoundException,
} from "./types/errors";
import { UnknownException } from "effect/Cause";
import type { ChapterFilter, TriggerEvent } from "./types/controllerTypes";
import type { AutoLabelRunOutput, CluenerParams, DoNothingParams } from "@/api/models";
import {
	ALRProvId,
	ALRServId,
	AProvId,
	AServId,
	CCProvId,
	CCServId,
	CProvId,
	CServId,
	type IDRepository,
	LGProvId,
	type ProvAutoLabel,
	type ProvAutoLabelRun,
} from "./types/idTypes";
import { Prov, IdempotentCallable, isAllReserveable, makeReservationRequest } from "./types/helperTypes";
import type { RequestEvent, ReserveList } from "./types/requestTypes";
import {
	CreateAutolabelsAutoLabelsPost200Response,
	CreateLabelDatasByAutoLabelsLabelGroupsLabelGroupIdLabelDatasAutoLabelsPost200Response,
	ReadAutoLabelRunsAutoLabelRunsGet200Response,
	ReadAutoLabelsByRunAutoLabelRunsRunIdAutoLabelsGet200Response,
	ReadAutolabelByIdAutoLabelsAutoLabelIdGet200Response,
} from "@/api/endpoints/default/default.effect";
import {
	createAutolabelsAutoLabelsPost,
	createLabelDatasByAutoLabelsLabelGroupsLabelGroupIdLabelDatasAutoLabelsPost,
	readAutoLabelRunsAutoLabelRunsGet,
	readAutoLabelsByRunAutoLabelRunsRunIdAutoLabelsGet,
	readAutolabelByIdAutoLabelsAutoLabelIdGet,
} from "@/api/endpoints/default/default";

export type AutolabelDataManager = {
	createAutoLabelRun: (
		params: CluenerParams | DoNothingParams,
		chapterFilter: ChapterFilter,
	) => Effect.Effect<RequestEvent[], UnknownException | FatalException>;
	promoteAutoLabelRun: (
		runId: ALRProvId,
		labelGroupId: LGProvId,
		chapterFilter: ChapterFilter,
	) => Effect.Effect<RequestEvent[], UnknownException | FatalException>;
	refreshAutoLabelRuns: () => Effect.Effect<RequestEvent[], UnknownException | FatalException>;
	reloadAutoLabelRun: (
		runId: ALRProvId,
	) => Effect.Effect<RequestEvent[], UnknownException | FatalException>;
	loadAutoLabelData: (
		autoLabelId: AProvId,
	) => Effect.Effect<RequestEvent[], UnknownException | FatalException>;
};

export const buildAutolabelDataManager = (
	novelId: string,
	raiseTriggerEvent: (event: TriggerEvent) => Effect.Effect<void>,
	idRepo: IDRepository,
	getters: {
		chapterIds: () => Effect.Effect<readonly CProvId[], UnknownException>;
		chapter: (chapterId: CProvId) => Effect.Effect<
			{
				chapterNum: number;
				cc:
					| {
							status: "ready";
							chapterContentId: CCProvId;
					  }
					| { status: "idle" | "loading" | "error" };
				chapterIsPublic: boolean;
			},
			NotFoundException
		>;
	},
	autoLabelRuns: AutoLabelRunOutput[],
): Effect.Effect<AutolabelDataManager, FatalException> =>
	Effect.gen(function* () {
		const { decorate } = buildRequestQueueDispatcher<RequestEvent>();

		const autoLabelRunIndex = yield* buildAutoLabelRunIndex();
		for (const run of autoLabelRuns) {
			const runProvId = yield* idRepo
				.newIdAndBindId({
					kind: "autoLabelRun",
					servId: ALRServId(run.runId),
				})
				.pipe(Effect.mapError((err) => new FatalException({ orig: err })));
			yield* autoLabelRunIndex
				.new(runProvId, { run: Prov({ ...run, runId: runProvId }) })
				.pipe(Effect.mapError((err) => new FatalException({ orig: err })));
		}

		const resolveChapterContentIds = (
			filter: ChapterFilter,
		): Effect.Effect<CCProvId[], UnknownException> =>
			Effect.gen(function* () {
				const ids = yield* getters.chapterIds();
				const result: CCProvId[] = [];
				for (const chId of ids) {
					const data = yield* getters
						.chapter(chId)
						.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
					const num = data.chapterNum;
					if (filter.start != null && num < filter.start) continue;
					if (filter.end != null && num >= filter.end) continue;
					if (filter.isPublic != null) {
						const isPub = data.chapterIsPublic;
						if (isPub !== filter.isPublic) continue;
					}
					const ccId = data.cc.status === "ready" ? data.cc.chapterContentId : null;
					if (ccId !== null) result.push(ccId);
				}
				return result;
			});

		const _createAutoLabelRun = (
			params: CluenerParams | DoNothingParams,
			chapterFilter: ChapterFilter,
		): Effect.Effect<RequestEvent[], UnknownException | FatalException> =>
			Effect.sync(() => {
				const reserveList = (): ReserveList => ({
					autoLabelRun: [],
					autoLabel: [],
					label: [],
					chapter: [],
					chapterContent: Effect.runSync(resolveChapterContentIds(chapterFilter)).map(
						(id) => ({
							id,
							kind: "chapterContent" as const,
							desiredState: "locked" as const,
						}),
					),
					labelData: [],
					labelGroup: [],
				});

				let runProvId: ALRProvId | null = null;
				let newALIds: AProvId[] = [];

				const onError = (): Effect.Effect<void> =>
					Effect.gen(function* () {
						if (runProvId) {
							yield* autoLabelRunIndex
								.delete(runProvId)
								.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
							yield* idRepo
								.reserveIdObjState({
									kind: "autoLabelRun",
									id: runProvId,
									desiredState: "detaching",
								})
								.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
							yield* idRepo
								.releaseIdObjStateOnSuccess({
									kind: "autoLabelRun",
									id: runProvId,
								})
								.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
						}

						for (const alId of newALIds) {
							yield* idRepo
								.reserveIdObjState({
									kind: "autoLabel",
									id: alId,
									desiredState: "detaching",
								})
								.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
							yield* idRepo
								.releaseIdObjStateOnSuccess({ kind: "autoLabel", id: alId })
								.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
						}
					});

				return [
					{
						cached: true,
						variant: "createAutoLabelRun" as const,
						active: true,
						retries: 3,
						reservationRequest: {
							reserveList: IdempotentCallable(reserveList),
							skip: () => false,
							wait: () =>
								isAllReserveable(idRepo, reserveList()).pipe(
									Effect.map((ready) => !ready),
								),
						},
						onFailure: onError,
						onFatalError: onError,
						preSend: () => Effect.succeed(void 0),
						send: (requestKey) =>
							Effect.gen(function* () {
								const resp = yield* Effect.tryPromise(() =>
									createAutolabelsAutoLabelsPost(
										{
											novelId,
											params,
											start: chapterFilter.start ?? null,
											end: chapterFilter.end ?? null,
											isPublic: chapterFilter.isPublic ?? null,
											chapterIds: null,
										},
										{ requestKey },
									),
								).pipe(
									Effect.mapError(
										(err) => new ConnectionException({ orig: err }),
									),
								);
								if (resp.status === 409 && resp.data.detail.cacheConflict) {
									return yield* Effect.fail(
										new CacheConflictException({ requestKey }),
									);
								}
								if (resp.status !== 200) {
									return yield* Effect.fail(
										new FatalException({
											orig: new Error(
												`Create autolabel run failed: ${resp.status}`,
											),
										}),
									);
								}
								return resp.data;
							}),
						postSend: (data) =>
							Effect.gen(function* () {
								const validated = yield* Schema.decodeUnknown(
									CreateAutolabelsAutoLabelsPost200Response,
								)(data).pipe(
									Effect.mapError((err) => new FatalException({ orig: err })),
								);
								runProvId = yield* idRepo
									.newIdAndBindId({
										kind: "autoLabelRun",
										servId: ALRServId(validated.run.runId),
									})
									.pipe(
										Effect.mapError((err) => new FatalException({ orig: err })),
									);
								yield* autoLabelRunIndex.new(runProvId, {
									run: Prov({ ...validated.run, runId: runProvId }),
								});
								yield* autoLabelRunIndex.setData(runProvId, {
									status: "ready",
									data: { index: yield* buildAutoLabelIndex() },
								});
								const provRun: ProvAutoLabelRun = Prov({
									...validated.run,
									runId: runProvId,
								});

								const autoLabels: Omit<ProvAutoLabel, "autoLabelData">[] = [];
								for (const al of validated.autolabels) {
									const alProvId = yield* idRepo
										.newIdAndBindId({
											kind: "autoLabel",
											servId: AServId(al.autoLabelMeta.autoLabelId),
										})
										.pipe(
											Effect.mapError(
												(err) => new FatalException({ orig: err }),
											),
										);
									newALIds.push(alProvId);
									const alIndexSlot = yield* autoLabelRunIndex.get(runProvId);
									if (alIndexSlot.status !== "ready") {
										return yield* Effect.fail(
											new FatalException({
												orig: new Error(
													"AutoLabelRun index not ready after creation",
												),
											}),
										);
									}

									const ccProvId = yield* idRepo
										.newIdAndBindId({
											kind: "chapterContent",
											servId: CCServId(al.autoLabelMeta.chapterContentId),
										})
										.pipe(
											Effect.mapError(
												(err) => new FatalException({ orig: err }),
											),
										);
									const cId = yield* idRepo.newIdAndBindId({
										kind: "chapter",
										servId: CServId(al.chapterId),
									});
									yield* alIndexSlot.data.index.new(alProvId, {
										autoLabel: {
											autoLabelMeta: Prov({
												...al.autoLabelMeta,
												autoLabelId: alProvId,
												chapterContentId: ccProvId,
												runId: runProvId,
											}),
											chapterId: cId,
										},
									});
									autoLabels.push(
										Prov({
											autoLabelId: alProvId,
											autoLabelLastJobId: al.autoLabelMeta.autoLabelLastJobId,
											autoLabelMessage: al.autoLabelMeta.autoLabelMessage,
											autoLabelStatus: al.autoLabelMeta.autoLabelStatus,
											chapterContentId: ccProvId,
											runId: runProvId,
										}),
									);
								}

								yield* raiseTriggerEvent({
									eventType: "autoLabelRunCreated",
									run: provRun,
									autoLabels,
								});
							}).pipe(Effect.mapError((err) => new FatalException({ orig: err }))),
					},
				];
			});

		const _promoteAutoLabelRun = (
			runId: ALRProvId,
			labelGroupId: LGProvId,
			chapterFilter: ChapterFilter,
		): Effect.Effect<RequestEvent[], UnknownException | FatalException> =>
			Effect.sync(() => {
				const reserveList = (): ReserveList => ({
					autoLabelRun: [{ id: runId, kind: "autoLabelRun", desiredState: "locked" }],
					labelGroup: [
						{ id: labelGroupId, kind: "labelGroup", desiredState: "updating" },
					],
					autoLabel: [],
					label: [],
					chapter: [],
					chapterContent: Effect.runSync(resolveChapterContentIds(chapterFilter)).map(
						(id) => ({
							id,
							kind: "chapterContent",
							desiredState: "locked",
						}),
					),
					labelData: [],
				});

				return [
					{
						cached: true,
						variant: "promoteAutoLabelRun",
						active: true,
						retries: 3,
						reservationRequest: {
							reserveList: IdempotentCallable(reserveList),
							skip: () => false,
							wait: () =>
								isAllReserveable(idRepo, reserveList()).pipe(
									Effect.map((ready) => !ready),
								),
						},
						onFailure: () => Effect.succeed(void 0),
						onFatalError: () => Effect.succeed(void 0),
						preSend: () => Effect.succeed(void 0),
						send: (requestKey) =>
							Effect.gen(function* () {
								const servRunId = yield* idRepo
									.getServerId({ kind: "autoLabelRun", provId: runId })
									.pipe(
										Effect.mapError((err) => new FatalException({ orig: err })),
									);
								const servLabelGroupId = yield* idRepo
									.getServerId({ kind: "labelGroup", provId: labelGroupId })
									.pipe(
										Effect.mapError((err) => new FatalException({ orig: err })),
									);
								if (!servRunId || !servLabelGroupId) {
									return yield* Effect.fail(
										new FatalException({
											orig: new Error("Missing server IDs for promote"),
										}),
									);
								}
								const resp = yield* Effect.tryPromise(() =>
									createLabelDatasByAutoLabelsLabelGroupsLabelGroupIdLabelDatasAutoLabelsPost(
										servLabelGroupId,
										{
											runId: servRunId,
											start: chapterFilter.start ?? null,
											end: chapterFilter.end ?? null,
											chapterIds: null,
										},
										{ requestKey },
									),
								).pipe(
									Effect.mapError(
										(err) => new ConnectionException({ orig: err }),
									),
								);
								if (resp.status === 409 && resp.data.detail.cacheConflict) {
									return yield* Effect.fail(
										new CacheConflictException({ requestKey }),
									);
								}
								if (resp.status !== 200) {
									return yield* Effect.fail(
										new FatalException({
											orig: new Error(
												`Promote autolabels failed: ${resp.status}`,
											),
										}),
									);
								}
								return resp.data;
							}),
						postSend: (data) =>
							Effect.gen(function* () {
								const validated = yield* Schema.decodeUnknown(
									CreateLabelDatasByAutoLabelsLabelGroupsLabelGroupIdLabelDatasAutoLabelsPost200Response,
								)(data).pipe(
									Effect.mapError((err) => new FatalException({ orig: err })),
								);

								const successEntries: {
									chapterId: CProvId;
									chapterContentId: CCProvId;
								}[] = [];
								for (const [servChapterId, servContentId] of validated.success) {
									const chProvId = yield* idRepo
										.newIdAndBindId({
											kind: "chapter",
											servId: CServId(servChapterId),
										})
										.pipe(
											Effect.mapError(
												(err) => new FatalException({ orig: err }),
											),
										);
									const ccProvId = yield* idRepo
										.newIdAndBindId({
											kind: "chapterContent",
											servId: CCServId(servContentId),
										})
										.pipe(
											Effect.mapError(
												(err) => new FatalException({ orig: err }),
											),
										);
									successEntries.push({
										chapterId: chProvId,
										chapterContentId: ccProvId,
									});
								}

								const errorEntries: {
									chapterId: CProvId;
									chapterContentId: CCProvId;
									error: string;
								}[] = [];
								for (const [
									servChapterId,
									servContentId,
									error,
								] of validated.errors) {
									const chProvId = yield* idRepo
										.newIdAndBindId({
											kind: "chapter",
											servId: CServId(servChapterId),
										})
										.pipe(
											Effect.mapError(
												(err) => new FatalException({ orig: err }),
											),
										);
									const ccProvId = yield* idRepo
										.newIdAndBindId({
											kind: "chapterContent",
											servId: CCServId(servContentId),
										})
										.pipe(
											Effect.mapError(
												(err) => new FatalException({ orig: err }),
											),
										);
									if (!chProvId || !ccProvId) {
										yield* raiseTriggerEvent({
											eventType: "errorOccured",
											from: "dataManager",
											error: new Error(
												`Failed to bind chapter ${servChapterId} or chapter content ${servContentId} in ID repo during promotion error handling.`,
											),
										});
										continue;
									}
									errorEntries.push({
										chapterId: chProvId,
										chapterContentId: ccProvId,
										error,
									});
								}

								yield* raiseTriggerEvent({
									eventType: "autoLabelRunPromoted",
									runId,
									labelGroupId,
									chapterFilter,
									success: successEntries,
									errors: errorEntries,
								});
							}).pipe(Effect.mapError((err) => new FatalException({ orig: err }))),
					},
				];
			});

		const _refreshAutoLabelRuns = (): Effect.Effect<
			RequestEvent[],
			UnknownException | FatalException
		> =>
			Effect.gen(function* () {
				const currentRunIds = yield* autoLabelRunIndex.getIds();
				const reserveList = (): ReserveList => ({
					autoLabelRun: currentRunIds.map((id) => ({
						id,
						kind: "autoLabelRun" as const,
						desiredState: "locked" as const,
					})),
					autoLabel: [],
					label: [],
					chapter: [],
					chapterContent: [],
					labelData: [],
					labelGroup: [],
				});

				return [
					{
						cached: false,
						variant: "refreshAutoLabelRuns" as const,
						active: false,
						retries: 3,
						reservationRequest: {
							reserveList: IdempotentCallable(reserveList),
							skip: () => false,
							wait: () =>
								isAllReserveable(idRepo, reserveList()).pipe(
									Effect.map((ready) => !ready),
								),
						},
						onFailure: () => Effect.succeed(void 0),
						onFatalError: () => Effect.succeed(void 0),
						preSend: () => Effect.succeed(void 0),
						send: () =>
							Effect.gen(function* () {
								const resp = yield* Effect.tryPromise(() =>
									readAutoLabelRunsAutoLabelRunsGet({ novelId }),
								).pipe(
									Effect.mapError(
										(err) => new ConnectionException({ orig: err }),
									),
								);
								if (resp.status !== 200) {
									return yield* Effect.fail(
										new FatalException({
											orig: new Error(
												`Read autolabel runs failed: ${resp.status}`,
											),
										}),
									);
								}
								return resp.data;
							}),
						postSend: (data) =>
							Effect.gen(function* () {
								const validated = yield* Schema.decodeUnknown(
									ReadAutoLabelRunsAutoLabelRunsGet200Response,
								)(data).pipe(
									Effect.mapError((err) => new FatalException({ orig: err })),
								);

								const existingIds = yield* autoLabelRunIndex.getIds();
								for (const id of existingIds) {
									yield* autoLabelRunIndex
										.delete(id)
										.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
								}

								for (const run of validated) {
									const runProvId = yield* idRepo
										.newIdAndBindId({
											kind: "autoLabelRun",
											servId: ALRServId(run.runId),
										})
										.pipe(
											Effect.mapError(
												(err) => new FatalException({ orig: err }),
											),
										);
									yield* autoLabelRunIndex.new(runProvId, {
										run: Prov({ ...run, runId: runProvId }),
									});
								}

								yield* raiseTriggerEvent({
									eventType: "autoLabelRunsRefreshed",
								});
							}).pipe(Effect.mapError((err) => new FatalException({ orig: err }))),
					},
				];
			});

		const _reloadAutoLabelRun = (
			runId: ALRProvId,
		): Effect.Effect<RequestEvent[], UnknownException | FatalException> =>
			Effect.gen(function* () {
				const slot = yield* autoLabelRunIndex
					.get(runId)
					.pipe(Effect.mapError((err) => new FatalException({ orig: err })));
				if (slot.status === "loading") return [];

				yield* autoLabelRunIndex
					.increment(runId)
					.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
				yield* autoLabelRunIndex
					.setData(runId, { status: "loading" })
					.pipe(Effect.catchAll(() => Effect.succeed(void 0)));

				let skipPhaseTwo = true;
				let oldAutoLabelIds: AProvId[] = [];

				if (slot.status === "ready" && slot.data) {
					const oldIndex = slot.data.index;
					oldAutoLabelIds = Effect.runSync(oldIndex.getIds());
					if (oldAutoLabelIds.length > 0) {
						skipPhaseTwo = false;
					}
				}

				const onError = (): Effect.Effect<void> =>
					Effect.gen(function* () {
						yield* autoLabelRunIndex
							.setData(runId, { status: "error" })
							.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
						yield* autoLabelRunIndex
							.decrement(runId)
							.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
					});

				const phaseOneReserveList = (): ReserveList => ({
					autoLabelRun: [{ id: runId, kind: "autoLabelRun", desiredState: "locked" }],
					autoLabel: [],
					label: [],
					chapter: [],
					chapterContent: [],
					labelData: [],
					labelGroup: [],
				});

				const phaseTwoReserveList = (): ReserveList => ({
					autoLabelRun: [],
					autoLabel: oldAutoLabelIds.map((id) => {
						const state = Effect.runSyncExit(
							idRepo.idObjState({ kind: "autoLabel", id }),
						);
						const desiredState =
							state._tag === "Success" && state.value === "pending"
								? ("killing" as const)
								: ("detaching" as const);
						return {
							id,
							kind: "autoLabel" as const,
							desiredState,
						};
					}),
					label: [],
					chapter: [],
					chapterContent: [],
					labelData: [],
					labelGroup: [],
				});

				return [
					{
						cached: false,
						variant: "reloadAutoLabelRun" as const,
						active: false,
						retries: 3,
						reservationRequest: {
							reserveList: IdempotentCallable(phaseOneReserveList),
							skip: () => false,
							wait: () =>
								isAllReserveable(idRepo, phaseOneReserveList()).pipe(
									Effect.map((ready) => !ready),
								),
						},
						onFailure: onError,
						onFatalError: onError,
						preSend: () => Effect.succeed(void 0),
						send: () =>
							Effect.gen(function* () {
								const servRunId = yield* idRepo
									.getServerId({ kind: "autoLabelRun", provId: runId })
									.pipe(
										Effect.mapError((err) => new FatalException({ orig: err })),
									);
								if (!servRunId) {
									return yield* Effect.fail(
										new FatalException({
											orig: new Error("Missing server ID for autolabel run"),
										}),
									);
								}
								const resp = yield* Effect.tryPromise(() =>
									readAutoLabelsByRunAutoLabelRunsRunIdAutoLabelsGet(servRunId),
								).pipe(
									Effect.mapError(
										(err) => new ConnectionException({ orig: err }),
									),
								);
								if (resp.status !== 200) {
									return yield* Effect.fail(
										new FatalException({
											orig: new Error(
												`Read autolabels by run failed: ${resp.status}`,
											),
										}),
									);
								}
								return resp.data;
							}),
						postSend: (data) =>
							Effect.gen(function* () {
								const validated = yield* Schema.decodeUnknown(
									ReadAutoLabelsByRunAutoLabelRunsRunIdAutoLabelsGet200Response,
								)(data).pipe(
									Effect.mapError((err) => new FatalException({ orig: err })),
								);

								const newIndex = yield* buildAutoLabelIndex();
								for (const al of validated) {
									const alProvId = yield* idRepo
										.newIdAndBindId({
											kind: "autoLabel",
											servId: AServId(al.autoLabelMeta.autoLabelId),
										})
										.pipe(
											Effect.mapError(
												(err) => new FatalException({ orig: err }),
											),
										);
									const ccProvId = yield* idRepo
										.newIdAndBindId({
											kind: "chapterContent",
											servId: CCServId(al.autoLabelMeta.chapterContentId),
										})
										.pipe(
											Effect.mapError(
												(err) => new FatalException({ orig: err }),
											),
										);
									const cId = yield* idRepo.newIdAndBindId({
										kind: "chapter",
										servId: CServId(al.chapterId),
									});
									yield* newIndex
										.new(alProvId, {
											autoLabel: {
												autoLabelMeta: Prov({
													...al.autoLabelMeta,
													autoLabelId: alProvId,
													chapterContentId: ccProvId,
													runId,
												}),
												chapterId: cId,
											},
										})
										.pipe(Effect.catchAll(() => Effect.succeed(void 0)));
								}

								yield* autoLabelRunIndex.setData(runId, {
									status: "ready",
									data: { index: newIndex },
								});
								yield* autoLabelRunIndex
									.decrement(runId)
									.pipe(Effect.catchAll(() => Effect.succeed(void 0)));

								yield* raiseTriggerEvent({
									eventType: "autoLabelRunReloaded",
									runId,
								});
							}).pipe(Effect.mapError((err) => new FatalException({ orig: err }))),
					},
					{
						cached: false,
						variant: "reloadAutoLabelRun" as const,
						active: false,
						retries: 1,
						reservationRequest: {
							skip: () => skipPhaseTwo,
							wait: () => Effect.succeed(false),
							reserveList: IdempotentCallable(phaseTwoReserveList),
						},
						onFailure: () => Effect.succeed(void 0),
						onFatalError: () => Effect.succeed(void 0),
						preSend: () => Effect.succeed(void 0),
						send: () => Effect.succeed(void 0),
						postSend: () => Effect.succeed(void 0),
					},
				];
			});

	const _loadAutoLabelData = (
			autoLabelId: AProvId,
		): Effect.Effect<RequestEvent[], UnknownException | FatalException> =>
			Effect.gen(function* () {
				let parentRunId: ALRProvId | null = null;
				const runIds = yield* autoLabelRunIndex.getIds();
				for (const rid of runIds) {
					const runSlot = yield* autoLabelRunIndex
						.get(rid)
						.pipe(
							Effect.mapError(
								(err) => new FatalException({ orig: err }),
							),
						);
					if (runSlot.status !== "ready" || !runSlot.data) continue;
					const ids = yield* runSlot.data.index.getIds();
					if (ids.includes(autoLabelId)) {
						parentRunId = rid;
						break;
					}
				}
				if (!parentRunId) {
					return yield* Effect.fail(
						new FatalException({
							orig: new Error(
								`AutoLabel ${autoLabelId} not found in any run index`,
							),
						}),
					);
				}

				const reserveList: ReserveList = {
					autoLabelRun: [
						{
							id: parentRunId,
							kind: "autoLabelRun",
							desiredState: "locked",
						},
					],
					autoLabel: [
						{
							id: autoLabelId,
							kind: "autoLabel",
							desiredState: "locked",
						},
					],
					label: [],
					chapter: [],
					chapterContent: [],
					labelData: [],
					labelGroup: [],
				};

				return [
					{
						cached: false,
						variant: "loadAutoLabelData" as const,
						active: false,
						retries: 3,
						reservationRequest: makeReservationRequest(idRepo, reserveList),
						onFailure: () => Effect.succeed(void 0),
						onFatalError: () => Effect.succeed(void 0),
						preSend: () => Effect.succeed(void 0),
						send: () =>
							Effect.gen(function* () {
								const servAlId = yield* idRepo
									.getServerId({ kind: "autoLabel", provId: autoLabelId })
									.pipe(
										Effect.mapError(
											(err) => new FatalException({ orig: err }),
										),
									);
								if (!servAlId) {
									return yield* Effect.fail(
										new FatalException({
											orig: new Error("Missing server ID for autolabel"),
										}),
									);
								}
								const resp = yield* Effect.tryPromise(() =>
									readAutolabelByIdAutoLabelsAutoLabelIdGet(servAlId),
								).pipe(
									Effect.mapError(
										(err) => new ConnectionException({ orig: err }),
									),
								);
								if (resp.status !== 200) {
									return yield* Effect.fail(
										new FatalException({
											orig: new Error(
												`Read autolabel failed: ${resp.status}`,
											),
										}),
									);
								}
								return resp.data;
							}),
						postSend: (data) =>
							Effect.gen(function* () {
								const validated = yield* Schema.decodeUnknown(
									ReadAutolabelByIdAutoLabelsAutoLabelIdGet200Response,
								)(data).pipe(
									Effect.mapError((err) => new FatalException({ orig: err })),
								);

								const runSlot = yield* autoLabelRunIndex
									.get(parentRunId)
									.pipe(
										Effect.mapError(
											(err) => new FatalException({ orig: err }),
										),
									);
								if (runSlot.status !== "ready" || !runSlot.data) {
									return yield* Effect.fail(
										new FatalException({
											orig: new Error(
												"Parent run not ready for autolabel data",
											),
										}),
									);
								}
								yield* runSlot.data.index.setData(autoLabelId, {
									status: "ready",
									data: {
										autoLabelData: validated.autoLabelData
											? [...validated.autoLabelData]
											: null,
									},
								});

								yield* raiseTriggerEvent({
									eventType: "autoLabelDataLoaded",
									autoLabelId,
								});
							}).pipe(Effect.mapError((err) => new FatalException({ orig: err }))),
					},
				];
			});

		return {
			createAutoLabelRun: decorate(_createAutoLabelRun),
			promoteAutoLabelRun: decorate(_promoteAutoLabelRun),
			refreshAutoLabelRuns: _refreshAutoLabelRuns,
			reloadAutoLabelRun: _reloadAutoLabelRun,
			loadAutoLabelData: _loadAutoLabelData,
		};
	});
