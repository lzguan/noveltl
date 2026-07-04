import { Effect, Schema } from "effect";
import { buildRequestQueueDispatcher } from "./dmHelpers";
import { CacheConflictException, ConnectionException, FatalException } from "./types/errors";
import { UnknownException } from "effect/Cause";
import type { ChapterFilter, TriggerEvent } from "./types/controllerTypes";
import type { CluenerParams, DoNothingParams } from "@/api/models";
import {
	ALRProvId,
	ALRServId,
	AServId,
	CProvId,
	CCProvId,
	CCServId,
	CServId,
	type IDRepository,
	LGProvId,
	type ProvAutoLabel,
	type ProvAutoLabelRun,
} from "./types/idTypes";
import { Prov, makeReservationRequest } from "./types/helperTypes";
import type { RequestEvent } from "./types/requestTypes";
import {
	CreateAutolabelsAutoLabelsPost200Response,
	CreateLabelDatasByAutoLabelsLabelGroupsLabelGroupIdLabelDatasAutoLabelsPost200Response,
} from "@/api/endpoints/default/default.effect";
import {
	createAutolabelsAutoLabelsPost,
	createLabelDatasByAutoLabelsLabelGroupsLabelGroupIdLabelDatasAutoLabelsPost,
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
};

export const buildAutolabelDataManager = (
	novelId: string,
	raiseTriggerEvent: (event: TriggerEvent) => Effect.Effect<void>,
	idRepo: IDRepository,
): AutolabelDataManager => {
	const { decorate } = buildRequestQueueDispatcher<RequestEvent>();

	const _createAutoLabelRun = (
		params: CluenerParams | DoNothingParams,
		chapterFilter: ChapterFilter,
	): Effect.Effect<RequestEvent[], UnknownException | FatalException> =>
		Effect.sync(() => {
			return [
				{
					cached: true,
					variant: "createAutoLabelRun" as const,
					active: true,
					retries: 3,
					reservationRequest: makeReservationRequest(idRepo, {
						autoLabelRun: [],
						autoLabel: [],
						label: [],
						chapter: [],
						chapterContent: [],
						labelData: [],
						labelGroup: [],
					}),
					onFailure: () => Effect.succeed(void 0),
					onFatalError: () => Effect.succeed(void 0),
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
								Effect.mapError((err) => new ConnectionException({ orig: err })),
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
							const runProvId = yield* idRepo
								.newIdAndBindId("autoLabelRun", ALRServId(validated.run.runId))
								.pipe(Effect.mapError((err) => new FatalException({ orig: err })));

							const provRun: ProvAutoLabelRun = Prov({
								...validated.run,
								runId: runProvId,
							});

							const autoLabels: Omit<ProvAutoLabel, "autoLabelData">[] = [];
							for (const al of validated.autolabels) {
								const alProvId = yield* idRepo
									.newIdAndBindId("autoLabel", AServId(al.autoLabelId))
									.pipe(
										Effect.mapError((err) => new FatalException({ orig: err })),
									);
								const ccProvId = yield* idRepo
									.newIdAndBindId("chapterContent", CCServId(al.chapterContentId))
									.pipe(
										Effect.mapError((err) => new FatalException({ orig: err })),
									);
								autoLabels.push(
									Prov({
										autoLabelId: alProvId,
										autoLabelLastJobId: al.autoLabelLastJobId,
										autoLabelMessage: al.autoLabelMessage,
										autoLabelStatus: al.autoLabelStatus,
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
			return [
				{
					cached: true,
					variant: "promoteAutoLabelRun" as const,
					active: true,
					retries: 3,
					reservationRequest: makeReservationRequest(idRepo, {
						autoLabelRun: [{ id: runId, kind: "autoLabelRun", desiredState: "locked" }],
						labelGroup: [
							{ id: labelGroupId, kind: "labelGroup", desiredState: "locked" },
						],
						autoLabel: [],
						label: [],
						chapter: [],
						chapterContent: [],
						labelData: [],
					}),
					onFailure: () => Effect.succeed(void 0),
					onFatalError: () => Effect.succeed(void 0),
					preSend: () => Effect.succeed(void 0),
					send: (requestKey) =>
						Effect.gen(function* () {
							const servRunId = yield* idRepo
								.getServerId("autoLabelRun", runId)
								.pipe(Effect.mapError((err) => new FatalException({ orig: err })));
							const servLabelGroupId = yield* idRepo
								.getServerId("labelGroup", labelGroupId)
								.pipe(Effect.mapError((err) => new FatalException({ orig: err })));
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
								Effect.mapError((err) => new ConnectionException({ orig: err })),
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
									.newIdAndBindId("chapter", CServId(servChapterId))
									.pipe(
										Effect.mapError((err) => new FatalException({ orig: err })),
									);

								const ccProvId = yield* idRepo
									.newIdAndBindId("chapterContent", CCServId(servContentId))
									.pipe(
										Effect.mapError((err) => new FatalException({ orig: err })),
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
							for (const [servChapterId, servContentId, error] of validated.errors) {
								const chProvId = yield* idRepo
									.newIdAndBindId("chapter", CServId(servChapterId))
									.pipe(
										Effect.mapError((err) => new FatalException({ orig: err })),
									);
								const ccProvId = yield* idRepo
									.newIdAndBindId("chapterContent", CCServId(servContentId))
									.pipe(
										Effect.mapError((err) => new FatalException({ orig: err })),
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

	return {
		createAutoLabelRun: decorate(_createAutoLabelRun),
		promoteAutoLabelRun: decorate(_promoteAutoLabelRun),
	};
};
