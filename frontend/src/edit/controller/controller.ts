import { Effect } from "effect";
import type {
	NovelController,
	NovelGetters,
	NovelUserEvent,
	TriggerEvent,
} from "./types/controllerTypes";
import { type NovelData, buildNovelDataManager } from "./dataManager";
import { buildRequestManager } from "./requestmanager";
import { buildIdRepository } from "./idRepository";
import type { RequestEvent } from "./types/requestTypes";
import type { ConnectionException, FatalException } from "./types/errors";
import type { TimeoutException, UnknownException } from "effect/Cause";
import { buildPubSub } from "../utils/pubsub";

export const buildNovelController = (
	novelData: NovelData,
): Effect.Effect<NovelController, ConnectionException | FatalException | TimeoutException> =>
	Effect.gen(function* () {
		const idRepo = buildIdRepository();

		const { subscribe, raiseTriggerEvent } = buildPubSub<NovelGetters, TriggerEvent>();

		const novelDM = yield* buildNovelDataManager(
			() => Effect.succeed(novelData),
			raiseTriggerEvent,
			idRepo,
		);

		const requestManager = yield* buildRequestManager(idRepo, (event) =>
			raiseTriggerEvent(novelDM.getters, event),
		);

		let running = false;

		const dispatch = (effect: Effect.Effect<RequestEvent[], unknown>): Effect.Effect<void> =>
			Effect.gen(function* () {
				const result = yield* effect.pipe(
					Effect.catchAll((err) => {
						return raiseTriggerEvent(novelDM.getters, {
							eventType: "errorOccured",
							from: "dataManager",
							error: (() => {
								if (err instanceof Error) return err;
								if (typeof err !== "object" || err === null)
									return new Error(String(err));
								if ("cause" in err) {
									const c = err.cause;
									if (typeof c === "object" && c !== null && "message" in c)
										return new Error(String(c.message));
								}
								if ("message" in err) return new Error(String(err.message));
								return new Error(String(err));
							})(),
						}).pipe(Effect.andThen(() => Effect.succeed<RequestEvent[]>([])));
					}),
				);

				for (const event of result) {
					requestManager.enqueueRequest(event);
				}
			});

		const handleUserEvent = (event: NovelUserEvent): Effect.Effect<void> =>
			Effect.gen(function* () {
				if (!running) return Effect.succeed(undefined);
				console.log("handleUserEvent", event.eventType, new Date().toISOString());

				switch (event.eventType) {
					case "textOp": {
						const chapterDM = novelDM.getChapterDM(event.chapterId);
						if (!chapterDM) {
							yield* raiseTriggerEvent(novelDM.getters, {
								eventType: "errorOccured",
								from: "dataManager",
								error: new Error(`Chapter ${event.chapterId} is not loaded`),
							});
							break;
						}
						if (event.op.op === "insert") {
							yield* dispatch(chapterDM.insertTextAt(event.op.start, event.op.text));
						} else {
							yield* dispatch(
								chapterDM.deleteTextAt(
									event.op.start,
									event.op.start + event.op.text.length,
								),
							);
						}
						break;
					}
					case "labelOp": {
						const chapterDM = novelDM.getChapterDM(event.chapterId);
						if (!chapterDM) {
							yield* raiseTriggerEvent(novelDM.getters, {
								eventType: "errorOccured",
								from: "dataManager",
								error: new Error(`Chapter ${event.chapterId} is not loaded`),
							});
							break;
						}
						if (event.op.op === "add") {
							yield* dispatch(
								chapterDM.addLabel(
									event.labelGroupId,
									event.op.startPos,
									event.op.endPos,
									event.op.word,
									event.op.entityGroup ?? undefined,
									event.op.score ?? undefined,
									event.op.dirty ?? undefined,
								),
							);
						} else if (event.op.op === "delete") {
							yield* dispatch(
								chapterDM.deleteLabel(
									event.labelGroupId,
									event.op.startPos,
									event.op.endPos,
								),
							);
						} else {
							yield* dispatch(
								chapterDM.updateLabel(
									event.labelGroupId,
									event.op.startPos,
									event.op.endPos,
									event.op.newStartPos,
									event.op.newEndPos,
									event.op.newWord,
									event.op.entityGroup ?? undefined,
									event.op.score ?? undefined,
									event.op.dirty ?? undefined,
								),
							);
						}
						break;
					}
					case "addLabelGroup": {
						yield* dispatch(novelDM.addLabelGroup(event.labelGroupName));
						break;
					}
					case "addChapter": {
						yield* dispatch(
							novelDM.addChapter(
								event.chapterNum,
								event.chapterTitle,
								event.chapterIsPublic,
							),
						);
						break;
					}
					case "openChapter": {
						yield* dispatch(
							novelDM.openChapter(
								event.chapterId,
								event.eagerLabelGroupIds,
								event.flags,
							),
						);
						break;
					}
					case "closeChapter": {
						const chapterDM = novelDM.getChapterDM(event.chapterId);
						if (!chapterDM) {
							yield* raiseTriggerEvent(novelDM.getters, {
								eventType: "errorOccured",
								from: "dataManager",
								error: new Error(`Chapter ${event.chapterId} is not loaded`),
							});
							break;
						}
						yield* dispatch(chapterDM.destroy());
						break;
					}
					case "loadLabelData": {
						const chapterDM = novelDM.getChapterDM(event.chapterId);
						if (!chapterDM) {
							yield* raiseTriggerEvent(novelDM.getters, {
								eventType: "errorOccured",
								from: "dataManager",
								error: new Error(`Chapter ${event.chapterId} is not loaded`),
							});
							break;
						}
						yield* dispatch(chapterDM.reloadGroup(event.labelGroupId, true));
						break;
					}
				}

				yield* requestManager.debounce();
			});

		const start = (): Effect.Effect<void, UnknownException> => {
			running = true;
			return Effect.gen(function* () {
				yield* requestManager.start();
				yield* Effect.repeat(
					Effect.gen(function* () {
						yield* dispatch(novelDM.flush()).pipe(
							Effect.tapError((err) =>
								raiseTriggerEvent(novelDM.getters, {
									eventType: "errorOccured",
									from: "dataManager",
									error: err,
								}).pipe(
									Effect.andThen(() => {
										running = false;
									}),
								),
							),
						);
						yield* Effect.sleep("1 second");
					}),
					{ until: () => !running },
				);
			});
		};

		const stop = (): Effect.Effect<void> => {
			running = false;

			return requestManager.waitFlush().pipe(
				Effect.catchAll((err) => {
					return raiseTriggerEvent(novelDM.getters, {
						eventType: "errorOccured",
						from: "dataManager",
						error: err,
					});
				}),
			);
		};

		return {
			handleUserEvent,
			getters: novelDM.getters,
			subscribe,
			start,
			stop,
		};
	});
