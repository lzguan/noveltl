import { Effect, Schema } from "effect";
import { buildLabelDataIndex, buildRequestQueueDispatcher } from "./dmHelpers";
import {
	CacheConflictException,
	ConnectionException,
	FatalException,
	NotFoundException,
} from "./types/errors";
import { UnknownException } from "effect/Cause";
import type { TriggerEvent } from "./types/controllerTypes";
import {
	CCServId,
	CProvId,
	type IDRepository,
	type InFlightIdStatus,
	LDProvId,
	LDServId,
	LGProvId,
	LGServId,
	LProvId,
	type ProvLabel,
} from "./types/idTypes";
import {
	IdempotentCallable,
	isAllReserveable,
	Prov,
	type LabelGroupSlot,
} from "./types/helperTypes";
import type { Novel, TextOp } from "@/api/models";
import type { RequestEvent, Reservation, ReserveList } from "./types/requestTypes";
import type { LabelOp } from "./types/dataTypes";
import {
	ReadEditChapterDataEditChapterDataChapterIdPost200Response,
	ReadEditChapterLabelDataEditChapterDataChapterIdLabelDataPost200Response,
	UpdateChapterContentChaptersChapterIdContentPatch200Response,
} from "@/api/endpoints/default/default.effect";
import {
	readEditChapterLabelDataEditChapterDataChapterIdLabelDataPost,
	updateChapterContentChaptersChapterIdContentPatch,
	updateLabelDataStreamLabelDatasLabelDataIdPatch,
} from "@/api/endpoints/default/default";
import type { Role } from "@/api/models/role";
import type { ChapterDataManager } from "./types/dataTypes";

export const buildChapterDataManager = (
	editChapterData: typeof ReadEditChapterDataEditChapterDataChapterIdPost200Response.Type,
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
		let chapterContentId = yield* idRepo
			.newIdAndBindId({
				kind: "chapterContent",
				servId: CCServId(editChapterData.chapterContent.chapterContentId),
			})
			.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
		let text = editChapterData.chapterContent.chapterContentText;

		const labelDataIndex = yield* buildLabelDataIndex().pipe(
			Effect.mapError((err) => new UnknownException({ orig: err })),
		);
		// scoped for initialization
		{
			const labelGroupProvIds = yield* getters.labelGroupIds();
			for (const lgProvId of labelGroupProvIds) {
				const lgSlot = yield* getters
					.labelGroup(lgProvId)
					.pipe(Effect.catchAll(() => Effect.succeed(null)));
				if (!lgSlot) {
					continue;
				}
				const lgServId = yield* idRepo
					.getServerId({
						kind: "labelGroup",
						provId: lgSlot.meta.labelGroup.labelGroupId,
					})
					.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
				if (lgServId === null) {
					return yield* Effect.fail(
						new UnknownException({
							message: `Unexpected: label group ${lgProvId} does not have a server id`,
						}),
					);
				}
			}

			for (const entry of editChapterData.eagerLabelData) {
				const provLdId = yield* idRepo
					.newIdAndBindId({
						kind: "labelData",
						servId: LDServId(entry.labelData.labelDataId),
					})
					.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
				const provLabels: ProvLabel[] = entry.labels
					.map((l) => {
						const provLabelId = Effect.runSync(
							idRepo.newIdAndBindExists({ kind: "label" }),
						);
						return Prov({
							...l,
							labelId: provLabelId,
							labelDataId: provLdId,
						});
					})
					.sort((a, b) => a.labelStart - b.labelStart);
				const servId = LGServId(entry.labelGroup.labelGroupId);
				const lgProvId = yield* idRepo.queryProvId({ kind: "labelGroup", servId });
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
				const provLdId = yield* idRepo
					.newIdAndBindId({
						kind: "labelData",
						servId: LDServId(entry.labelData.labelDataId),
					})
					.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
				const servId = LGServId(entry.labelGroup.labelGroupId);
				const lgProvId = yield* idRepo.queryProvId({ kind: "labelGroup", servId });
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

		const { decorate: decorateQueued, flush: flushQueued } =
			buildRequestQueueDispatcher<RequestEvent>();

		const lockChapter = (events: RequestEvent[]): RequestEvent[] => {
			for (const event of events) {
				const chapterReservations = event.reservationRequest.reserveList().chapter;
				if (!chapterReservations.some((reservation) => reservation.id === chapterId)) {
					chapterReservations.push({
						id: chapterId,
						kind: "chapter",
						desiredState: "locked",
					});
				}
			}
			return events;
		};

		const decorate = <Params extends unknown[], E>(
			f: (...params: Params) => Effect.Effect<RequestEvent[], E>,
		) => {
			const queued = decorateQueued<Params, E>(f);
			return (...params: Params): Effect.Effect<RequestEvent[], E> =>
				queued(...params).pipe(Effect.map(lockChapter));
		};

		const dispatcherFlush = (): Effect.Effect<RequestEvent[]> =>
			flushQueued().pipe(Effect.map(lockChapter));

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
							autoLabel: [],
							autoLabelRun: [],
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
										.getServerId({ kind: "labelData", provId: labelDataProvId })
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
											yield* idRepo.bindServerExists({
												kind: "label",
												provId: labelId,
											});
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
							autoLabel: [],
							autoLabelRun: [],
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
						cached: true,
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
						send: (requestKey) =>
							Effect.gen(function* () {
								const servContentId = yield* idRepo
									.getServerId({
										kind: "chapterContent",
										provId: chapterContentId,
									})
									.pipe(
										Effect.mapError(
											(err) => new ConnectionException({ orig: err }),
										),
									);
								const servChapterId = yield* idRepo
									.getServerId({
										kind: "chapter",
										provId: chapterId,
									})
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
								chapterContentId = yield* idRepo
									.newIdAndBindId({
										kind: "chapterContent",
										servId: CCServId(validated.chapterContentId),
									})
									.pipe(
										Effect.mapError((err) => new FatalException({ orig: err })),
									);
								for (const lgId of yield* labelDataIndex.getIds()) {
									const slot = yield* labelDataIndex.get(lgId);
									const ldId = slot.meta.labelData.labelDataId;
									const oldServId = yield* idRepo
										.getServerId({
											kind: "labelData",
											provId: ldId,
										})
										.pipe(Effect.catchAll(() => Effect.succeed(null)));
									if (oldServId && validated.labelDataIdMap[oldServId]) {
										const newId = yield* idRepo
											.newIdAndBindId({
												kind: "labelData",
												servId: LDServId(
													validated.labelDataIdMap[oldServId],
												),
											})
											.pipe(
												Effect.mapError(
													(err) => new FatalException({ orig: err }),
												),
											);
										yield* labelDataIndex.setMeta(lgId, {
											labelData: Prov({
												labelDataId: newId,
												labelGroupId: lgId,
												chapterContentId: chapterContentId,
											}),
										});
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
				const labelGroupSlot = yield* getters.labelGroup(labelGroupId).pipe(
					Effect.mapError(
						(err) =>
							new UnknownException({
								message: `Label group ${labelGroupId} not found in getters, error: ${err}`,
							}),
					),
				);
				const slot = yield* labelDataIndex
					.get(labelGroupId)
					.pipe(
						Effect.catch("_tag", {
							failure: "NotFoundException",
							onFailure: () =>
								Effect.gen(function* () {
									yield* labelDataIndex.new(labelGroupId, {
										labelData: Prov({
											labelDataId: idRepo.newId("labelData"),
											chapterContentId,
											labelGroupId,
										}),
									});
									return yield* labelDataIndex.get(labelGroupId);
								}),
						}),
					)
					.pipe(Effect.mapError((err) => new UnknownException({ orig: err })));
				if (slot.status !== "ready" || !slot.data) {
					return yield* Effect.fail(
						new UnknownException({
							message: `Labels for group ${labelGroupId} not loaded`,
						}),
					);
				}
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
				const insertIds = yield* labelDataIndex.getIds();
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
						.pipe(
							Effect.mapError(
								(err) =>
									new UnknownException({
										message: `Failed to update label data, error: ${String(err)}`,
									}),
							),
						);
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
				const deleteIds = yield* labelDataIndex.getIds();
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
						.pipe(
							Effect.mapError(
								(err) =>
									new UnknownException({
										message: `Failed to update label data, error: ${String(err)}`,
										orig: err,
									}),
							),
						);
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
				yield* labelDataIndex.setData(labelGroupId, { status: "loading" }).pipe(
					Effect.mapError(
						(err) =>
							new UnknownException({
								message: `Failed to set label data index to loading for group ${labelGroupId}`,
								orig: err,
							}),
					),
				);
				yield* labelDataIndex.increment(labelGroupId).pipe(
					Effect.mapError(
						(err) =>
							new UnknownException({
								message: `Failed to increment label data index for group ${labelGroupId}`,
								orig: err,
							}),
					),
				);

				const oldLabelDataProvId = slot.meta.labelData.labelDataId;
				const oldLabelIds: LProvId[] =
					slot.status === "ready" && slot.data
						? slot.data.labels.map((l) => l.labelId)
						: [];
				let skip = false;
				let wait = true;

				const onError = () =>
					Effect.gen(function* () {
						yield* labelDataIndex.setData(labelGroupId, { status: "error" }).pipe(
							Effect.catchAll((err) => {
								Effect.logError(
									`Failed to set label data index to error for group ${labelGroupId}, error: ${err}`,
								);
								return Effect.succeed(void 0);
							}),
						);
						yield* labelDataIndex.decrement(labelGroupId).pipe(
							Effect.catchAll((err) => {
								Effect.logError(
									`Failed to decrement label data index for group ${labelGroupId}, error: ${err}`,
								);
								return Effect.succeed(void 0);
							}),
						);
						wait = false;
					});

				const reloadReserveList: () => ReserveList = () => {
					const oldLabelDataServId = Effect.runSyncExit(
						idRepo.getServerId({ kind: "labelData", provId: oldLabelDataProvId }),
					);
					return {
						autoLabel: [],
						autoLabelRun: [],
						chapter: [],
						chapterContent: [],
						labelGroup: [
							{ id: labelGroupId, kind: "labelGroup", desiredState: "locked" },
						],
						labelData:
							oldLabelDataServId._tag === "Success" &&
							oldLabelDataServId.value !== null
								? [
										{
											id: oldLabelDataProvId,
											kind: "labelData",
											desiredState: "locked",
										},
									]
								: [],
						label: oldLabelIds.map((id) => ({
							id,
							kind: "label" as const,
							desiredState: "detaching" as const,
						})),
					};
				};

				const detachReserveList: () => ReserveList = () => {
					const curLabelDataState = Effect.runSyncExit(
						idRepo.idObjState({ kind: "labelData", id: oldLabelDataProvId }),
					);
					if (curLabelDataState._tag === "Failure") {
						return {
							autoLabel: [],
							autoLabelRun: [],
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
						autoLabel: [],
						autoLabelRun: [],
						chapter: [],
						chapterContent: [],
						labelGroup: [
							{ id: labelGroupId, kind: "labelGroup", desiredState: "locked" },
						],
						labelData: [
							{
								id: oldLabelDataProvId,
								kind: "labelData",
								desiredState,
							},
						],
						label: [],
					};
				};

				const event: RequestEvent = {
					cached: false,
					variant: "reloadGroup",
					active: false,
					retries: 3,
					reservationRequest: {
						reserveList: IdempotentCallable(reloadReserveList),
						skip: () => skip,
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
								.getServerId({ kind: "chapter", provId: chapterId })
								.pipe(Effect.mapError((err) => new FatalException({ orig: err })));
							const servLabelGroupId = yield* idRepo
								.getServerId({ kind: "labelGroup", provId: labelGroupId })
								.pipe(Effect.mapError((err) => new FatalException({ orig: err })));
							if (!servChapterId || !servLabelGroupId) {
								return yield* Effect.fail(
									new FatalException({
										orig: new Error("Missing server IDs for reload group"),
									}),
								);
							}
							const resp = yield* Effect.tryPromise(() =>
								readEditChapterLabelDataEditChapterDataChapterIdLabelDataPost(
									servChapterId,
									[servLabelGroupId],
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
								ReadEditChapterLabelDataEditChapterDataChapterIdLabelDataPost200Response,
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
							const newLabelDataProvId = yield* idRepo
								.newIdAndBindId({
									kind: "labelData",
									servId: LDServId(entry.labelData.labelDataId),
								})
								.pipe(Effect.mapError((err) => new FatalException({ orig: err })));
							if (newLabelDataProvId === oldLabelDataProvId) {
								skip = true;
							}
							const provLabels: ProvLabel[] = entry.labels
								.map((l) => {
									const provLabelId = Effect.runSync(
										idRepo.newIdAndBindExists({ kind: "label" }),
									);
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
								.pipe(
									Effect.mapError(
										(err) =>
											new FatalException({
												orig: err,
											}),
									),
								);
							yield* labelDataIndex
								.setData(labelGroupId, {
									status: "ready",
									data: { labels: provLabels },
								})
								.pipe(Effect.mapError((err) => new FatalException({ orig: err })));
							yield* labelDataIndex
								.decrement(labelGroupId)
								.pipe(Effect.mapError((err) => new FatalException({ orig: err })));
							yield* raiseTriggerEvent({
								eventType: "labelDataLoaded",
								labelGroupId,
								chapterId,
								wasDeleted: false,
							});
							wait = false;
						}),
				};
				const flushedOps = yield* autoFlushIfTagMismatch("neither");
				return [
					...flushedOps,
					event,
					{
						cached: false,
						variant: "reloadGroup",
						active: false,
						retries: 1,
						reservationRequest: {
							skip: () => skip,
							wait: () => Effect.succeed(wait),
							reserveList: IdempotentCallable(detachReserveList),
						},
						onFailure: () => Effect.succeed(void 0),
						onFatalError: () => Effect.succeed(void 0),
						preSend: () => Effect.succeed(void 0),
						send: () => Effect.succeed(void 0),
						postSend: () => Effect.succeed(void 0),
					},
				];
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

		const destroy = (): Effect.Effect<RequestEvent[], UnknownException> =>
			Effect.gen(function* () {
				if (destroyed) return [];
				destroyed = true;
				const events = yield* flush();
				events.push(...(yield* dispatcherFlush()));
				return events;
			});

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
				chapterContentId: () => Effect.succeed(chapterContentId),
				isDestroyed: () => destroyed,
			},
		};
	});
