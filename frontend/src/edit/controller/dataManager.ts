import { createLogger } from "@/lib/logging";
import type { ChapterControllerEntry, LoadingStatus, NovelDataManager } from "./types/dataTypes";
import type { Chapter, LabelGroup, Novel } from "@/api/models";
import { Effect, Schema } from "effect";
import { FatalException, ConnectionException } from "./types/errors";
import type { TimeoutException } from "effect/Cause";
import { ProvId, ServId, type IDRepository } from "./types/idTypes";
import type { RequestEvent } from "./types/requestTypes";
import { makeReservationRequest, Prov } from "./types/helperTypes";
import type { TriggerEvent } from "./types/controllerTypes";
import { createLabelGroupLabelGroupsPost } from "@/api/endpoints/default/default";
import { CreateLabelGroupLabelGroupsPost200Response } from "@/api/endpoints/default/default.effect";

const logger = createLogger("DataManager");

interface HasActiveAttribute {
	active: boolean;
}

type Dequeuer<T extends HasActiveAttribute, Params extends unknown[]> = (
	...params: [...Params]
) => T[];

type RequestQueueDispatcher<T extends HasActiveAttribute> = {
	decorate: <Params extends unknown[]>(f: Dequeuer<T, Params>) => Dequeuer<T, Params>;
	flush: () => T[];
};

function buildRequestQueueDispatcher<T extends HasActiveAttribute>(): RequestQueueDispatcher<T> {
	const queue: T[] = [];
	const decorate =
		<Params extends unknown[]>(f: Dequeuer<T, Params>) =>
		(...params: [...Params]) => {
			const result = f(...params);
			const out: T[] = [];
			for (const item of result) {
				if (item.active) {
					out.push(...queue);
					queue.length = 0;
					out.push(item);
				} else {
					queue.push(item);
				}
			}
			return out;
		};

	const flush = () => {
		const out = [...queue];
		queue.length = 0;
		return out;
	};

	return {
		decorate,
		flush,
	};
}

type NovelData = {
	novel: Novel;
	chapters: Chapter[];
	labelGroups: LabelGroup[];
};

export const buildNovelDataManager = (
	fetchNovelData: () => Effect.Effect<NovelData, ConnectionException | TimeoutException>,
	raiseTriggerEvent: (event: TriggerEvent) => void,
	idRepo: IDRepository,
): Effect.Effect<unknown, ConnectionException | TimeoutException> =>
	Effect.gen(function* () {
		const novelData = yield* fetchNovelData();

		const controllers: Map<ProvId, ChapterControllerEntry> = new Map(
			novelData.chapters.map<[ProvId, ChapterControllerEntry]>((val) => {
				const chapterId = idRepo.newIdAndBindId("chapter", ServId(val.chapterId));
				return [
					ProvId(chapterId),
					{ status: "notLoaded", chapter: Prov<Chapter>({ ...val, chapterId: chapterId }) },
				];
			}),
		);
		const labelGroups: Map<ProvId, { labelGroup: Prov<LabelGroup>; loadingStatus: LoadingStatus }> =
			new Map(
				novelData.labelGroups.map<
					[ProvId, { labelGroup: Prov<LabelGroup>; loadingStatus: LoadingStatus }]
				>((val) => {
					const newId = idRepo.newIdAndBindId("labelGroup", ServId(val.labelGroupId));
					return [
						ProvId(val.labelGroupId),
						{
							labelGroup: Prov<LabelGroup>({ ...val, labelGroupId: newId }),
							loadingStatus: "loaded",
						},
					];
				}),
			);

		const { decorate } = buildRequestQueueDispatcher<RequestEvent>();

		const _addLabelGroup = (labelGroupName: string): RequestEvent[] => {
			const newId = idRepo.newId("labelGroup");
			const newLabelGroup: Prov<LabelGroup> = Prov({
				labelGroupId: newId,
				labelGroupName,
				novelId: novelData.novel.novelId,
			});
			labelGroups.set(newId, { labelGroup: newLabelGroup, loadingStatus: "notLoaded" });
			raiseTriggerEvent({ eventType: "labelGroupAdded", labelGroup: newLabelGroup });
			const onError = () => {
				const groupEntry = labelGroups.get(newId);
				if (groupEntry) {
					labelGroups.set(newId, {
						labelGroup: groupEntry.labelGroup,
						loadingStatus: "loadError",
					});
				}
			};

			return [
				{
					cached: false,
					reservationRequest: makeReservationRequest(idRepo, [
						{
							id: newId,
							desiredState: "creating",
							kind: "labelGroup",
						},
					]),
					variant: "addLabelGroup",
					onFailure: onError,
					onFatalError: onError,
					retries: 3,
					active: true,
					preSend: () => {},
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
							const validated = yield* Schema.validate(CreateLabelGroupLabelGroupsPost200Response)(
								data,
							);
							idRepo.bindServerId("labelGroup", newId, ServId(validated.labelGroupId));
						}).pipe(Effect.mapError((err) => new FatalException({ orig: err }))),
				},
			];
		};
		const addLabelGroup = decorate(_addLabelGroup);
		const _addChapter = (
			chapterNum: number,
			chapterTitle: string,
			chapterIsPublic: boolean,
		): RequestEvent[] => {
			const newId = idRepo.newId("chapter");
		};

		return {
			addLabelGroup,
		};
	});

export function buildDataManager(
	ents: DataEntry[],
	idRepo: IDRepository,
	novel: Novel,
	chapter: Chapter,
	userId: string,
	initialChapterContentId: ProvisionalId,
	initialText: string,
): DataManager {
	let entries: DataEntry[] = ents;
	let text: string = initialText;
	let labelGroupSyncHandler: () => void = () => {};

	const chapterContentId: ProvisionalId = initialChapterContentId;
	let labelOpQueue: Map<ProvisionalId, { labelId: ProvisionalId; op: LabelOp }[]> = new Map();
	let textOpQueue: { op: TextOp; labelDataIds: ProvisionalId[]; labelIds: ProvisionalId[] }[] = [];

	const ensureNoPendingTextOps = () => {
		if (textOpQueue.length > 0) {
			throw new Error("Cannot mutate labels while text operations are pending flush.");
		}
	};

	const ensureNoPendingLabelOps = () => {
		const hasPendingLabelOps = Array.from(labelOpQueue.values()).some((ops) => ops.length > 0);
		if (hasPendingLabelOps) {
			throw new Error("Cannot mutate text while label operations are pending flush.");
		}
	};

	const queueLabelOp = (labelGroupId: ProvisionalId, labelId: ProvisionalId, op: LabelOp) => {
		if (!labelOpQueue.has(labelGroupId)) {
			labelOpQueue.set(labelGroupId, []);
		}
		labelOpQueue.get(labelGroupId)!.push({ labelId, op });
	};

	const getMatchingLabelIndex = (entry: DataEntry, startPos: number, endPos: number) => {
		return entry.labels.findIndex(
			(label) => label.labelStart === startPos && label.labelEnd === endPos,
		);
	};

	const addLabelGroup = (labelGroupName: string): [ProvisionalId, RequestEvent[]] => {
		const provisionalGroupId = idRepo.newId("labelGroup");
		const provisionalDataId = idRepo.newId("labelData");
		const newLabelGroup: ProvisionalLabelGroup = {
			labelGroupId: provisionalGroupId,
			labelGroupName: labelGroupName,
			novelId: novel.novelId,
			provisional: true,
		};
		const newEntries = [...entries];
		const contentIdSnapshot = chapterContentId;
		newEntries.unshift({
			labelGroup: newLabelGroup,
			labelData: {
				labelDataId: provisionalDataId,
				labelGroupId: provisionalGroupId,
				chapterContentId: contentIdSnapshot,
				provisional: true,
			},
			labels: [],
			role: "owner",
			loadingStatus: "notLoaded",
		});
		entries = newEntries;
		labelGroupSyncHandler();
		let skipRemaining = false;

		const cleanupAddLabelGroupFailure = () => {
			const entry = entries.find(
				(candidate) => candidate.labelGroup.labelGroupId === provisionalGroupId,
			);
			if (entry) {
				entry.loadingStatus = "loadError";
			}
			skipRemaining = true;
			if (idRepo.isReserveable("labelData", provisionalDataId, "killing")) {
				idRepo.reserveIdObjState("labelData", provisionalDataId, "killing");
				idRepo.releaseIdObjStateOnSuccess("labelData", provisionalDataId);
			} else if (idRepo.isReserveable("labelData", provisionalDataId, "detaching")) {
				idRepo.reserveIdObjState("labelData", provisionalDataId, "detaching");
				idRepo.releaseIdObjStateOnSuccess("labelData", provisionalDataId);
			}
			labelGroupSyncHandler();
		};

		return [
			provisionalGroupId,
			[
				{
					variant: "addLabelGroup",
					retries: 3,
					callback: async (requestKey) => {
						let resp;
						try {
							resp = await createLabelGroupLabelGroupsPost({
								body: {
									novelId: novel.novelId,
									labelGroupName: labelGroupName,
								},
								query: {
									requestKey: requestKey,
								},
							});
						} catch (err) {
							logger.error("Failed to create label group", {
								error: err,
								requestKey,
							});
							throw new ConnectionError("Failed to create label group", err);
						}
						if (!resp.data) {
							if (isRequestConflictErrorResponse(resp.error) && resp.error.detail.cacheConflict) {
								throw new CacheConflictError(
									"Request key conflict while creating label group",
									requestKey,
								);
							} else if (isDetailHttpErrorResponse(resp.error)) {
								throw new FatalError(
									`Failed to create label group: ${resp.error.detail}`,
									resp.error,
								);
							}
							throw new FatalError("Failed to create label group", resp.error);
						}
						idRepo.bindServerId("labelGroup", provisionalGroupId, resp.data.labelGroupId);
						return null;
					},
					handleCachedResult: (cachedResult, requestKey) => {
						if (cachedResult.status === "success") {
							const validated = validateData(isLabelGroup, cachedResult.response);
							idRepo.bindServerId("labelGroup", provisionalGroupId, validated.labelGroupId);
							return { status: cachedResult.status, signal: null, error: null };
						} else if (cachedResult.status === "pending") {
							return { status: cachedResult.status, signal: null, error: null };
						} else {
							if (cachedResult.error?.cacheConflict) {
								return {
									status: cachedResult.status,
									signal: null,
									error: new CacheConflictError(
										"Request key conflict while creating label group",
										requestKey,
									),
								};
							}
						}
						return {
							status: cachedResult.status,
							signal: null,
							error: new FatalError(
								"Failed to create label group",
								cachedResult.error instanceof Error
									? cachedResult.error
									: new Error(JSON.stringify(cachedResult.error)),
							),
						};
					},
					reservationRequest: {
						reserveList: [
							{
								id: provisionalGroupId,
								kind: "labelGroup",
								desiredState: "creating",
							},
						],
						skip: () => skipRemaining,
					},

					onFailure: cleanupAddLabelGroupFailure,
					onFatalError: cleanupAddLabelGroupFailure,
				},
				{
					variant: "addLabelGroup",
					retries: 3,
					callback: async (requestKey) => {
						let resp;
						try {
							resp = await createLabelDataLabelGroupsLabelGroupIdLabelDatasPost({
								body: {
									chapterContentId: idRepo.getServerId("chapterContent", contentIdSnapshot)!,
								},
								path: {
									labelGroupId: idRepo.getServerId("labelGroup", provisionalGroupId)!,
								},
								query: {
									requestKey: requestKey,
								},
							});
						} catch (err) {
							logger.error("Failed to create label data", {
								error: err,
								requestKey,
								labelGroupId: idRepo.getServerId("labelGroup", provisionalGroupId)!,
							});
							throw new ConnectionError("Failed to create label data", err);
						}
						if (!resp.data) {
							if (isRequestConflictErrorResponse(resp.error) && resp.error.detail.cacheConflict) {
								throw new CacheConflictError(
									"Request key conflict while creating label data",
									requestKey,
								);
							} else if (isDetailHttpErrorResponse(resp.error)) {
								throw new FatalError(
									`Failed to create label data: ${resp.error.detail}`,
									resp.error,
								);
							}
							throw new FatalError("Failed to create label data", resp.error);
						}
						idRepo.bindServerId("labelData", provisionalDataId, resp.data.labelDataId);
						entries.find(
							(entry) => entry.labelGroup.labelGroupId === provisionalGroupId,
						)!.loadingStatus = "loaded";
						labelGroupSyncHandler();
						return null;
					},
					handleCachedResult: (cachedResult, requestKey) => {
						if (cachedResult.status === "success") {
							const validated = validateData(isLabelData, cachedResult.response);
							idRepo.bindServerId("labelData", provisionalDataId, validated.labelDataId);
							entries.find(
								(entry) => entry.labelGroup.labelGroupId === provisionalGroupId,
							)!.loadingStatus = "loaded";
							labelGroupSyncHandler();
							return { status: cachedResult.status, signal: null, error: null };
						} else if (cachedResult.status === "pending") {
							return { status: cachedResult.status, signal: null, error: null };
						} else {
							if (cachedResult.error?.cacheConflict) {
								return {
									status: cachedResult.status,
									signal: null,
									error: new CacheConflictError(
										"Request key conflict while creating label data",
										requestKey,
									),
								};
							}
							return {
								status: cachedResult.status,
								signal: null,
								error: new FatalError(
									"Failed to create label data",
									cachedResult.error instanceof Error
										? cachedResult.error
										: new Error(JSON.stringify(cachedResult.error)),
								),
							};
						}
					},
					reservationRequest: {
						reserveList: [
							{ id: provisionalDataId, kind: "labelData", desiredState: "creating" },
							{ id: provisionalGroupId, kind: "labelGroup", desiredState: "locked" },
							{
								id: contentIdSnapshot,
								kind: "chapterContent",
								desiredState: "locked",
							},
						],
						skip: () => skipRemaining,
					},
					onFailure: cleanupAddLabelGroupFailure,
					onFatalError: cleanupAddLabelGroupFailure,
				},
			],
		];
	};

	const addLabel = (
		labelGroupId: string,
		labelDataId: string,
		startPos: number,
		endPos: number,
		word: string,
		entityGroup?: string,
		score?: number,
		dirty?: boolean,
	): ProvisionalId => {
		ensureNoPendingTextOps();
		if (startPos < 0 || startPos >= endPos || endPos > text.length) {
			throw new Error("Label bounds are out of range");
		}
		if (word.length !== endPos - startPos) {
			throw new Error("Label word length must match label bounds");
		}
		if (text.slice(startPos, endPos) !== word) {
			throw new Error("Label word must match the current chapter text");
		}
		const provisionalLabelId = idRepo.newId("label");
		const entriesCopy = [...entries];
		const entryIndex = entriesCopy.findIndex((e) => e.labelGroup.labelGroupId === labelGroupId);
		if (entryIndex === -1) {
			throw new Error(`Label group with id ${labelGroupId} not found`);
		}
		const entry = entriesCopy[entryIndex];
		if (entry.labels.some((l) => Math.max(l.labelStart, startPos) < Math.min(l.labelEnd, endPos))) {
			// if any label overlaps with [startPos, endPos)
			throw new Error("Label overlaps with existing label");
		}

		entriesCopy[entryIndex].labels.push({
			labelId: provisionalLabelId,
			labelDataId: labelDataId,
			labelStart: startPos,
			labelEnd: endPos,
			labelWord: word,
			provisional: true,
			labelDirty: dirty ?? true,
			labelEntityGroup: entityGroup ?? null,
			labelScore: score ?? 1.0,
		});
		entriesCopy[entryIndex].labels.sort((left, right) => left.labelStart - right.labelStart);
		queueLabelOp(labelGroupId, provisionalLabelId, {
			op: "add",
			startPos: startPos,
			endPos: endPos,
			word: word,
			entityGroup: entityGroup ?? null,
			score: score ?? 1.0,
			dirty: dirty ?? true,
		});
		entries = entriesCopy;
		return provisionalLabelId;
	};

	const deleteLabel = (
		labelGroupId: string,
		labelDataId: string,
		startPos: number,
		endPos: number,
	): ProvisionalId => {
		ensureNoPendingTextOps();
		const entriesCopy = [...entries];
		const entryIndex = entriesCopy.findIndex(
			(entry) => entry.labelGroup.labelGroupId === labelGroupId,
		);
		if (entryIndex === -1) {
			throw new Error(`Label group with id ${labelGroupId} not found`);
		}
		const entry = entriesCopy[entryIndex];
		const labelIndex = getMatchingLabelIndex(entry, startPos, endPos);
		if (labelIndex === -1) {
			throw new Error(`Label [${startPos}, ${endPos}) not found in label group ${labelGroupId}`);
		}
		const label = entry.labels[labelIndex];
		if (label.labelDataId !== labelDataId) {
			throw new Error(`Label does not belong to label data ${labelDataId}`);
		}

		entriesCopy[entryIndex] = {
			...entry,
			labels: entry.labels.filter((_, idx) => idx !== labelIndex),
		};
		queueLabelOp(labelGroupId, label.labelId, {
			op: "delete",
			startPos: label.labelStart,
			endPos: label.labelEnd,
			word: label.labelWord,
		});
		entries = entriesCopy;
		return label.labelId;
	};

	const updateLabel = (
		labelGroupId: string,
		labelDataId: string,
		startPos: number,
		endPos: number,
		newStartPos?: number | null,
		newEndPos?: number | null,
		newWord?: string | null,
		entityGroup?: string,
		score?: number,
		dirty?: boolean,
	): ProvisionalId => {
		ensureNoPendingTextOps();
		const entriesCopy = [...entries];
		const entryIndex = entriesCopy.findIndex(
			(entry) => entry.labelGroup.labelGroupId === labelGroupId,
		);
		if (entryIndex === -1) {
			throw new Error(`Label group with id ${labelGroupId} not found`);
		}
		const entry = entriesCopy[entryIndex];
		const labelIndex = getMatchingLabelIndex(entry, startPos, endPos);
		if (labelIndex === -1) {
			throw new Error(`Label [${startPos}, ${endPos}) not found in label group ${labelGroupId}`);
		}
		const currentLabel = entry.labels[labelIndex];
		if (currentLabel.labelDataId !== labelDataId) {
			throw new Error(`Label does not belong to label data ${labelDataId}`);
		}

		const nextStart = newStartPos ?? currentLabel.labelStart;
		const nextEnd = newEndPos ?? currentLabel.labelEnd;
		const boundsChanged = newStartPos != null || newEndPos != null;
		if (!boundsChanged && newWord != null) {
			throw new Error("Cannot set a new label word without changing label bounds");
		}
		const nextWord =
			newWord ?? (boundsChanged ? text.slice(nextStart, nextEnd) : currentLabel.labelWord);
		if (nextStart >= nextEnd) {
			throw new Error("Updated label must have start < end");
		}
		if (nextStart < 0 || nextEnd > text.length) {
			throw new Error("Updated label bounds are out of range");
		}
		if (nextWord.length !== nextEnd - nextStart) {
			throw new Error("Updated label word length must match updated bounds");
		}
		if (text.slice(nextStart, nextEnd) !== nextWord) {
			throw new Error("Updated label word must match the current chapter text");
		}
		const overlapsExisting = entry.labels.some((label, idx) => {
			if (idx === labelIndex) {
				return false;
			}
			return Math.max(label.labelStart, nextStart) < Math.min(label.labelEnd, nextEnd);
		});
		if (overlapsExisting) {
			throw new Error("Updated label overlaps with existing label");
		}

		entriesCopy[entryIndex] = {
			...entry,
			labels: entry.labels
				.map((label, idx) => {
					if (idx !== labelIndex) {
						return label;
					}
					return {
						...label,
						labelStart: nextStart,
						labelEnd: nextEnd,
						labelWord: nextWord,
						labelEntityGroup: entityGroup ?? label.labelEntityGroup,
						labelScore: score ?? label.labelScore,
						labelDirty: dirty ?? label.labelDirty,
					};
				})
				.sort((left, right) => left.labelStart - right.labelStart),
		};

		queueLabelOp(labelGroupId, currentLabel.labelId, {
			op: "update",
			startPos: currentLabel.labelStart,
			endPos: currentLabel.labelEnd,
			word: currentLabel.labelWord,
			newStartPos: nextStart !== currentLabel.labelStart ? nextStart : undefined,
			newEndPos: nextEnd !== currentLabel.labelEnd ? nextEnd : undefined,
			newWord: nextWord !== currentLabel.labelWord ? nextWord : undefined,
			entityGroup: entityGroup ?? undefined,
			score: score ?? undefined,
			dirty: dirty ?? undefined,
		});
		entries = entriesCopy;
		return currentLabel.labelId;
	};

	const flushLabelOps = (): RequestEvent[] => {
		const queuedOps = Array.from(labelOpQueue.entries()).filter(([, ops]) => ops.length > 0);
		labelOpQueue = new Map();
		return queuedOps.map(([labelGroupId, queuedLabelOps]) => {
			const entry = entries.find((candidate) => candidate.labelGroup.labelGroupId === labelGroupId);
			if (!entry) {
				throw new Error(`Label group with id ${labelGroupId} not found while flushing label ops`);
			}
			const currentLabelIds = new Set(entry.labels.map((label) => label.labelId));
			const reserveList: { id: ProvisionalId; kind: Kind; desiredState: InFlightIdStatus }[] = [
				{
					id: entry.labelData.labelDataId,
					kind: "labelData",
					desiredState: "updating",
				},
				{ id: chapterContentId, kind: "chapterContent", desiredState: "locked" },
			];
			const reservedLabelIds = new Set<ProvisionalId>();
			for (const { labelId } of queuedLabelOps) {
				if (reservedLabelIds.has(labelId)) {
					continue;
				}
				reservedLabelIds.add(labelId);
				const currentState = idRepo.idObjState("label", labelId);
				const labelStillExists = currentLabelIds.has(labelId);
				if (currentState === "pending" && !labelStillExists) {
					continue;
				}
				if (currentState === "pending") {
					reserveList.push({ id: labelId, kind: "label", desiredState: "creating" });
				} else if (labelStillExists) {
					reserveList.push({ id: labelId, kind: "label", desiredState: "updating" });
				} else {
					reserveList.push({ id: labelId, kind: "label", desiredState: "deleting" });
				}
			}
			return {
				variant: "labelOp",
				retries: 3,
				reservationRequest: {
					reserveList,
				},

				callback: async (requestKey) => {
					let resp;
					try {
						resp = await updateLabelDataStreamLabelDatasLabelDataIdPatch({
							path: {
								labelDataId: idRepo.getServerId("labelData", entry.labelData.labelDataId)!,
							},
							body: {
								ops: queuedLabelOps.map(({ op }) => op),
							},
							query: {
								requestKey: requestKey,
							},
						});
					} catch (err) {
						logger.error("Failed to update label data stream", {
							error: err,
							labelDataId: idRepo.getServerId("labelData", entry.labelData.labelDataId)!,
							requestKey,
						});
						throw new ConnectionError("Failed to update label data stream", err);
					}
					if (resp.error) {
						if (isRequestConflictErrorResponse(resp.error) && resp.error.detail.cacheConflict) {
							throw new CacheConflictError(
								"Request key conflict while updating label data stream",
								requestKey,
							);
						} else if (isDetailHttpErrorResponse(resp.error)) {
							throw new FatalError(
								`Failed to update label data stream: ${resp.error.detail}`,
								resp.error,
							);
						}
						throw new FatalError("Failed to update label data stream", resp.error);
					}

					for (const { labelId, op } of queuedLabelOps) {
						if (op.op === "add" && currentLabelIds.has(labelId)) {
							idRepo.bindServerExists("label", labelId);
						}
					}
					return null;
				},
				handleCachedResult: (cachedResult, requestKey) => {
					if (cachedResult.status === "success") {
						for (const { labelId, op } of queuedLabelOps) {
							if (op.op === "add" && currentLabelIds.has(labelId)) {
								idRepo.bindServerExists("label", labelId);
							}
						}
						return { status: cachedResult.status, signal: null, error: null };
					} else if (cachedResult.status === "pending") {
						return { status: cachedResult.status, signal: null, error: null };
					} else {
						if (cachedResult.error?.cacheConflict) {
							return {
								status: cachedResult.status,
								signal: null,
								error: new CacheConflictError(
									"Request key conflict while updating label data stream",
									requestKey,
								),
							};
						}
						return {
							status: cachedResult.status,
							signal: null,
							error: new FatalError(
								"Failed to update label data stream",
								cachedResult.error instanceof Error
									? cachedResult.error
									: new Error(JSON.stringify(cachedResult.error)),
							),
						};
					}
				},
			};
		});
	};

	const insertTextAt = (pos: number, insertedText: string): void => {
		ensureNoPendingLabelOps();
		const currentText = text;
		if (pos < 0 || pos > currentText.length) {
			throw new Error("Insert position is out of bounds");
		}
		if (insertedText.length === 0) {
			return;
		}
		const affectedLabelDataIds = entries.map((entry) => entry.labelData.labelDataId);
		const affectedLabelIds = entries.flatMap((entry) => entry.labels.map((label) => label.labelId));
		const delta = insertedText.length;
		const nextEntries = entries.map((entry) => {
			const nextLabels = entry.labels
				.filter((label) => label.labelEnd <= pos || label.labelStart >= pos)
				.map((label) => {
					if (label.labelStart >= pos) {
						return {
							...label,
							labelStart: label.labelStart + delta,
							labelEnd: label.labelEnd + delta,
						};
					}
					return label;
				})
				.sort((left, right) => left.labelStart - right.labelStart);
			return {
				...entry,
				labels: nextLabels,
			};
		});
		entries = nextEntries;
		text = currentText.slice(0, pos) + insertedText + currentText.slice(pos);
		textOpQueue.push({
			op: {
				op: "insert",
				start: pos,
				text: insertedText,
			},
			labelDataIds: affectedLabelDataIds,
			labelIds: affectedLabelIds,
		});
	};

	const deleteTextAt = (startPos: number, length: number): void => {
		ensureNoPendingLabelOps();
		const currentText = text;
		const endPos = startPos + length;
		if (
			startPos < 0 ||
			startPos > currentText.length ||
			endPos < startPos ||
			endPos > currentText.length
		) {
			throw new Error("Delete text range is out of bounds");
		}
		const deletedText = currentText.slice(startPos, endPos);
		if (deletedText.length === 0) {
			return;
		}
		const affectedLabelDataIds = entries.map((entry) => entry.labelData.labelDataId);
		const affectedLabelIds = entries.flatMap((entry) => entry.labels.map((label) => label.labelId));
		const delta = deletedText.length;
		const nextEntries = entries.map((entry) => {
			const nextLabels = entry.labels
				.filter((label) => label.labelEnd <= startPos || label.labelStart >= endPos)
				.map((label) => {
					if (label.labelStart >= endPos) {
						return {
							...label,
							labelStart: label.labelStart - delta,
							labelEnd: label.labelEnd - delta,
						};
					}
					return label;
				})
				.sort((left, right) => left.labelStart - right.labelStart);
			return {
				...entry,
				labels: nextLabels,
			};
		});
		entries = nextEntries;
		text = currentText.slice(0, startPos) + currentText.slice(endPos);
		textOpQueue.push({
			op: {
				op: "delete",
				start: startPos,
				text: deletedText,
			},
			labelDataIds: affectedLabelDataIds,
			labelIds: affectedLabelIds,
		});
	};

	const flushTextOps = (): RequestEvent[] => {
		if (textOpQueue.length === 0) {
			return [];
		}
		const queuedTextOps = [...textOpQueue];
		textOpQueue = [];
		const currentChapterContentId = chapterContentId;
		const reserveLabelDataIds = Array.from(
			new Set(queuedTextOps.flatMap(({ labelDataIds }) => labelDataIds)),
		);
		const reserveLabelIds = Array.from(new Set(queuedTextOps.flatMap(({ labelIds }) => labelIds)));
		const snapshot = [...entries];
		return [
			{
				variant: "textOp",
				retries: 3,
				reservationRequest: {
					reserveList: [
						{
							id: currentChapterContentId,
							kind: "chapterContent",
							desiredState: "updating",
						},
						...reserveLabelDataIds.map((labelDataId) => ({
							id: labelDataId,
							kind: "labelData" as const,
							desiredState: "idUpdating" as const,
						})),
						...reserveLabelIds.map((labelId) => ({
							id: labelId,
							kind: "label" as const,
							desiredState: "updating" as const,
						})),
					],
				},
				callback: async (requestKey) => {
					let resp;
					try {
						resp = await updateChapterContentChaptersChapterIdContentPatch({
							path: {
								chapterId: chapter.chapterId,
							},
							body: {
								chapterContentId: idRepo.getServerId("chapterContent", currentChapterContentId)!,
								textOps: queuedTextOps.map(({ op }) => op),
							},
							query: {
								requestKey: requestKey,
							},
						});
					} catch (err) {
						logger.error("Failed to modify chapter content", {
							error: err,
							chapterContentId: idRepo.getServerId("chapterContent", currentChapterContentId)!,
							requestKey,
						});
						throw new ConnectionError("Failed to modify chapter content", err);
					}
					if (!resp.data) {
						if (isRequestConflictErrorResponse(resp.error) && resp.error.detail.cacheConflict) {
							throw new CacheConflictError(
								"Request key conflict while modifying chapter content",
								requestKey,
							);
						} else if (isDetailHttpErrorResponse(resp.error)) {
							throw new FatalError(
								`Failed to modify chapter content: ${resp.error.detail}`,
								resp.error,
							);
						}
						throw new FatalError("Failed to modify chapter content", resp.error);
					}
					idRepo.bindServerId(
						"chapterContent",
						currentChapterContentId,
						resp.data.chapterContentId,
					);
					for (const entry of snapshot) {
						const oldServerLabelDataId = idRepo.getServerId(
							"labelData",
							entry.labelData.labelDataId,
						);
						if (oldServerLabelDataId === null) {
							throw new Error(
								`Label data ${entry.labelData.labelDataId} is not bound to a server id`,
							);
						}
						const nextServerLabelDataId = resp.data.labelDataIdMap[oldServerLabelDataId];
						if (!nextServerLabelDataId) {
							throw new Error(
								`Missing label data remap for server label data id ${oldServerLabelDataId}`,
							);
						}
						idRepo.bindServerId("labelData", entry.labelData.labelDataId, nextServerLabelDataId);
					}
					return null;
				},
				handleCachedResult: (cachedResult, requestKey) => {
					if (cachedResult.status === "success") {
						const validated = validateData(isModifyChapterContentResponse, cachedResult.response);
						idRepo.bindServerId(
							"chapterContent",
							currentChapterContentId,
							validated.chapterContentId,
						);
						for (const entry of snapshot) {
							const oldServerLabelDataId = idRepo.getServerId(
								"labelData",
								entry.labelData.labelDataId,
							);
							if (oldServerLabelDataId === null) {
								throw new Error(
									`Label data ${entry.labelData.labelDataId} is not bound to a server id`,
								);
							}
							const nextServerLabelDataId = validated.labelDataIdMap[oldServerLabelDataId];
							if (!nextServerLabelDataId) {
								throw new Error(
									`Missing label data remap for server label data id ${oldServerLabelDataId}`,
								);
							}
							idRepo.bindServerId("labelData", entry.labelData.labelDataId, nextServerLabelDataId);
						}
						return { status: cachedResult.status, signal: null, error: null };
					} else if (cachedResult.status === "pending") {
						return { status: cachedResult.status, signal: null, error: null };
					} else {
						if (cachedResult.error?.cacheConflict) {
							return {
								status: cachedResult.status,
								signal: null,
								error: new CacheConflictError(
									"Request key conflict while modifying chapter content",
									requestKey,
								),
							};
						}
						return {
							status: cachedResult.status,
							signal: null,
							error: new FatalError(
								"Failed to modify chapter content",
								cachedResult.error instanceof Error
									? cachedResult.error
									: new Error(JSON.stringify(cachedResult.error)),
							),
						};
					}
				},
			},
		];
	};

	const handleSignal = (signal: DecoratedSignal) => {
		logger.info("Received signal in data manager:", signal);
		return;
	};

	const getGroups = () => entries.map((entry) => entry.labelGroup);

	const reloadGroup = (labelGroupId: string): RequestEvent[] => {
		const entry = entries.find((e) => e.labelGroup.labelGroupId === labelGroupId);
		if (!entry) {
			throw new Error(`Label group with id ${labelGroupId} not found`);
		}
		if (entry.loadingStatus === "loading") {
			return [];
		}
		const contentIdSnapshot = entry.labelData.chapterContentId;
		const oldLabelDataSnapshot = entry.labelData;
		const oldLabelDataId = oldLabelDataSnapshot.labelDataId;
		const oldLabelsSnapshot = [...entry.labels];
		const oldLabelIds = oldLabelsSnapshot.map((label) => label.labelId);
		const newLabelDataId = idRepo.newId("labelData");
		entry.loadingStatus = "loading";
		labelGroupSyncHandler();
		let skipRemaining = false;

		const cleanupReloadFailure = () => {
			entry.loadingStatus = "loadError";
			skipRemaining = true;
			if (idRepo.isReserveable("labelData", newLabelDataId, "killing")) {
				idRepo.reserveIdObjState("labelData", newLabelDataId, "killing");
				idRepo.releaseIdObjStateOnSuccess("labelData", newLabelDataId);
			} else if (idRepo.isReserveable("labelData", newLabelDataId, "detaching")) {
				idRepo.reserveIdObjState("labelData", newLabelDataId, "detaching");
				idRepo.releaseIdObjStateOnSuccess("labelData", newLabelDataId);
			}
			labelGroupSyncHandler();
		};

		return [
			{
				variant: "reloadGroup",
				retries: 3,
				reservationRequest: {
					reserveList: [
						{
							id: entry.labelGroup.labelGroupId,
							kind: "labelGroup",
							desiredState: "updating",
						},
					],
					skip: () => skipRemaining,
				},
				callback: async () => {
					let resp;
					try {
						resp = await Promise.all([
							readLabelGroupLabelGroupsLabelGroupIdGet({
								path: {
									labelGroupId: idRepo.getServerId("labelGroup", entry.labelGroup.labelGroupId)!,
								},
							}),
							readLabelContributorsLabelGroupsLabelGroupIdContributorsGet({
								path: {
									labelGroupId: idRepo.getServerId("labelGroup", entry.labelGroup.labelGroupId)!,
								},
							}),
						]);
					} catch (err) {
						logger.error("Failed to read label group or contributors during reload", {
							error: err,
							labelGroupId: entry.labelGroup.labelGroupId,
						});
						throw new ConnectionError("Failed to read label group", err);
					}
					if (resp[0].error || resp[1].error) {
						logger.error("Failed to read label group or contributors during reload", {
							errors: [resp[0].error, resp[1].error],
							labelGroupId: entry.labelGroup.labelGroupId,
						});
						throw new FatalError("Failed to read label group", resp[0].error ?? resp[1].error);
					}
					entry.labelGroup = {
						...entry.labelGroup,
						labelGroupName: resp[0].data.labelGroupName,
					};
					const contributorMe = resp[1].data.find((contributor) => contributor.userId === userId);
					if (!contributorMe) {
						throw new FatalError("Current user is not a contributor to the label group");
					}
					entry.role = contributorMe.labelContributorRole;
					return null;
				},
				onFailure: cleanupReloadFailure,
				onFatalError: cleanupReloadFailure,
			},
			{
				variant: "reloadGroup",
				retries: 3,
				reservationRequest: {
					reserveList: [],
				},
				callback: async () => {
					entry.labels = [];
					return oldLabelIds.length > 0 ? { type: "clearLabels", labelIds: oldLabelIds } : null;
				},
				onFailure: cleanupReloadFailure,
				onFatalError: cleanupReloadFailure,
			},
			{
				variant: "reloadGroup",
				retries: 3,
				reservationRequest: {
					reserveList: makeIdempotent(() => [
						...((): Reservation[] => {
							if (idRepo.isReserveable("labelData", oldLabelDataId, "detaching")) {
								return [
									{
										id: oldLabelDataId,
										kind: "labelData",
										desiredState: "detaching",
									},
								];
							} else if (idRepo.isReserveable("labelData", oldLabelDataId, "killing")) {
								return [
									{
										id: oldLabelDataId,
										kind: "labelData",
										desiredState: "killing",
									},
								];
							} else {
								return [];
							}
						})(),
						...oldLabelsSnapshot
							.filter((label) => idRepo.isReserveable("label", label.labelId, "detaching"))
							.map((label): { id: string; kind: Kind; desiredState: InFlightIdStatus } => ({
								id: label.labelId,
								kind: "label",
								desiredState: "detaching",
							})),
						...oldLabelsSnapshot
							.filter(
								(label) =>
									!idRepo.isReserveable("label", label.labelId, "detaching") &&
									idRepo.isReserveable("label", label.labelId, "killing"),
							)
							.map((label): { id: string; kind: Kind; desiredState: InFlightIdStatus } => ({
								id: label.labelId,
								kind: "label",
								desiredState: "killing",
							})),
					]),
					skip: () => skipRemaining,
					wait: () => {
						return (
							isInFlight(idRepo.idObjState("labelData", oldLabelDataId)) ||
							oldLabelsSnapshot.some((label) =>
								isInFlight(idRepo.idObjState("label", label.labelId)),
							)
						);
					},
				},
				callback: async () => null,
				onFailure: cleanupReloadFailure,
				onFatalError: cleanupReloadFailure,
			},
			{
				variant: "reloadGroup",
				retries: 3,
				reservationRequest: {
					reserveList: [
						{
							id: entry.labelGroup.labelGroupId,
							kind: "labelGroup",
							desiredState: "locked",
						},
						{
							id: newLabelDataId,
							kind: "labelData",
							desiredState: "loading",
						},
					],
					skip: () => skipRemaining,
				},
				callback: async () => {
					let resp;
					try {
						resp = await readLabelDatasByGroupChaptersLabelDatasGet({
							query: {
								labelGroupId: idRepo.getServerId("labelGroup", entry.labelGroup.labelGroupId)!,
								start: chapter.chapterNum,
								end: chapter.chapterNum + 1,
							},
						});
					} catch (err) {
						logger.error("Failed to read label data", {
							error: err,
							labelGroupId: entry.labelGroup.labelGroupId,
						});
						throw new ConnectionError("Failed to read label data", err);
					}
					if (resp.error) {
						logger.error("Failed to read label data", {
							errors: [resp.error],
							labelGroupId: entry.labelGroup.labelGroupId,
						});
						throw new FatalError("Failed to read label data", resp.error);
					}
					if (resp.data.length === 0) {
						logger.error("No label data found for label group and chapter", {
							labelGroupId: entry.labelGroup.labelGroupId,
							chapterNum: chapter.chapterNum,
						});
						throw new FatalError("No label data found for label group and chapter");
					}
					idRepo.bindServerId("labelData", newLabelDataId, resp.data[0].labelDataId);
					entry.labelData = {
						...oldLabelDataSnapshot,
						labelDataId: newLabelDataId,
					};
					return null;
				},
				onFailure: cleanupReloadFailure,
				onFatalError: cleanupReloadFailure,
			},
			{
				variant: "reloadGroup",
				reservationRequest: {
					reserveList: [
						{
							id: contentIdSnapshot,
							kind: "chapterContent",
							desiredState: "locked",
						},
						{
							id: entry.labelGroup.labelGroupId,
							kind: "labelGroup",
							desiredState: "locked",
						},
						{
							id: newLabelDataId,
							kind: "labelData",
							desiredState: "locked",
						},
					],
					skip: () => skipRemaining,
				},
				retries: 3,
				callback: async () => {
					let resp;
					try {
						resp = await readLabelsByLabelDataLabelDatasLabelDataIdLabelsGet({
							path: {
								labelDataId: idRepo.getServerId("labelData", newLabelDataId)!,
							},
						});
					} catch (err) {
						logger.error("Failed to read labels for label data", {
							error: err,
							labelDataId: idRepo.getServerId("labelData", newLabelDataId)!,
						});
						throw new ConnectionError("Failed to read labels for label data", err);
					}
					if (resp.error) {
						logger.error("Failed to read labels for label data", {
							errors: [resp.error],
							labelDataId: idRepo.getServerId("labelData", newLabelDataId)!,
						});
						throw new FatalError("Failed to read labels for label data", resp.error);
					}
					const newLabels = resp.data.map(
						(label): ProvisionalLabel => ({
							...label,
							provisional: true,
							labelId: idRepo.newIdAndBindExists("label"),
						}),
					); // possible leak here if timeout but it doesn't really matter
					entry.labels = newLabels;
					entry.loadingStatus = "loaded";
					labelGroupSyncHandler();
					return {
						type: "groupLoaded",
						labelGroupId: entry.labelGroup.labelGroupId,
						getLabels: () => newLabels,
						mutable: entry.role === "editor" || entry.role === "owner",
					};
				},
				onFailure: cleanupReloadFailure,
				onFatalError: cleanupReloadFailure,
			},
		];
	};

	const getLabelDataId = (labelGroupId: string) => {
		const entry = entries.find((e) => e.labelGroup.labelGroupId === labelGroupId);
		if (!entry) {
			throw new Error(`Label group with id ${labelGroupId} not found`);
		}
		return entry.labelData.labelDataId;
	};

	const getRole = (labelGroupId: string) => {
		const entry = entries.find((e) => e.labelGroup.labelGroupId === labelGroupId);
		if (!entry) {
			throw new Error(`Label group with id ${labelGroupId} not found`);
		}
		return entry.role;
	};

	const getLabels = (labelGroupId: string) => {
		const entry = entries.find((e) => e.labelGroup.labelGroupId === labelGroupId);
		if (!entry) {
			throw new Error(`Label group with id ${labelGroupId} not found`);
		}
		return entry.labels;
	};

	const getLoadingStatus = (labelGroupId: string) => {
		const entry = entries.find((e) => e.labelGroup.labelGroupId === labelGroupId);
		if (!entry) {
			throw new Error(`Label group with id ${labelGroupId} not found`);
		}
		return entry.loadingStatus;
	};

	const getName = (labelGroupId: string) => {
		const entry = entries.find((e) => e.labelGroup.labelGroupId === labelGroupId);
		if (!entry) {
			throw new Error(`Label group with id ${labelGroupId} not found`);
		}
		return entry.labelGroup.labelGroupName;
	};

	const attachLabelGroupSyncHandler = (handler: () => void) => {
		labelGroupSyncHandler = handler;
	};

	const detachLabelGroupSyncHandler = () => {
		labelGroupSyncHandler = () => {};
	};

	return {
		addLabel: addLabel,
		addLabelGroup: addLabelGroup,
		deleteLabel,
		updateLabel,
		flushLabelOps,
		insertTextAt,
		deleteTextAt,
		flushTextOps,
		handleSignal,
		reloadGroup,

		getForGroup: {
			labelDataId: getLabelDataId,
			role: getRole,
			labels: getLabels,
			loadingStatus: getLoadingStatus,
			name: getName,
		},

		getGroups,
		attachLabelGroupSyncHandler,
		detachLabelGroupSyncHandler,
	};
}
