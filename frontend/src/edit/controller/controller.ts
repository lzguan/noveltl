import { Effect } from "effect";
import type {
	NovelController,
	NovelGetters,
	NovelUserEvent,
	SubscriberFn,
	TriggerEvent,
} from "./types/controllerTypes";
import { type NovelData, buildNovelDataManager } from "./dataManager";
import { buildRequestManager } from "./requestmanager";
import { buildIdRepository } from "./idRepository";
import type { RequestEvent } from "./types/requestTypes";
import type { ConnectionException, FatalException } from "./types/errors";
import type { TimeoutException } from "effect/Cause";

function buildControllerCore<GettersT, TriggerEventT>() {
	const subscribers = new Set<SubscriberFn<GettersT, TriggerEventT>>();

	const subscribe = (fn: SubscriberFn<GettersT, TriggerEventT>): (() => void) => {
		subscribers.add(fn);
		return () => {
			subscribers.delete(fn);
		};
	};

	const raiseTriggerEvent = (getters: GettersT, event: TriggerEventT): void => {
		for (const fn of subscribers) {
			Effect.runSync(fn(getters, event));
		}
	};

	return { subscribe, raiseTriggerEvent };
}

export const buildNovelController = (
	novelData: NovelData,
): Effect.Effect<NovelController, ConnectionException | FatalException | TimeoutException> =>
	Effect.gen(function* () {
		const idRepo = buildIdRepository();

		const { subscribe, raiseTriggerEvent } = buildControllerCore<NovelGetters, TriggerEvent>();

		const novelDM = yield* buildNovelDataManager(
			() => Effect.succeed(novelData),
			raiseTriggerEvent,
			idRepo,
		);

		const requestManager = yield* buildRequestManager(idRepo, (event) =>
			raiseTriggerEvent(novelDM.getters, event),
		);

		let running = false;
		let timer: ReturnType<typeof setInterval> | null = null;

		const dispatch = (effect: Effect.Effect<RequestEvent[], unknown>): void => {
			const result = Effect.runSync(
				effect.pipe(
					Effect.catchAll((err) => {
						raiseTriggerEvent(novelDM.getters, {
							eventType: "errorOccured",
							from: "dataManager",
							error: err instanceof Error ? err : new Error(String(err)),
						});
						return Effect.succeed<RequestEvent[]>([]);
					}),
				),
			);
			for (const event of result) {
				requestManager.enqueueRequest(event);
			}
		};

		const handleUserEvent = (event: NovelUserEvent): void => {
			if (!running) return;

			switch (event.eventType) {
				case "textOp": {
					const chapterDM = novelDM.getChapterDM(event.chapterId);
					if (!chapterDM) {
						raiseTriggerEvent(novelDM.getters, {
							eventType: "errorOccured",
							from: "dataManager",
							error: new Error(`Chapter ${event.chapterId} is not loaded`),
						});
						break;
					}
					if (event.op.op === "insert") {
						dispatch(chapterDM.insertTextAt(event.op.start, event.op.text));
					} else {
						dispatch(chapterDM.deleteTextAt(event.op.start, event.op.start + event.op.text.length));
					}
					break;
				}
				case "labelOp": {
					const chapterDM = novelDM.getChapterDM(event.chapterId);
					if (!chapterDM) {
						raiseTriggerEvent(novelDM.getters, {
							eventType: "errorOccured",
							from: "dataManager",
							error: new Error(`Chapter ${event.chapterId} is not loaded`),
						});
						break;
					}
					if (event.op.op === "add") {
						dispatch(
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
						dispatch(chapterDM.deleteLabel(event.labelGroupId, event.op.startPos, event.op.endPos));
					} else {
						dispatch(
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
					dispatch(novelDM.addLabelGroup(event.labelGroupName));
					break;
				}
				case "addChapter": {
					dispatch(novelDM.addChapter(event.chapterNum, event.chapterTitle, event.chapterIsPublic));
					break;
				}
				case "openChapter": {
					dispatch(novelDM.openChapter(event.chapterId, [], true));
					break;
				}
				case "closeChapter": {
					const chapterDM = novelDM.getChapterDM(event.chapterId);
					if (!chapterDM) {
						raiseTriggerEvent(novelDM.getters, {
							eventType: "errorOccured",
							from: "dataManager",
							error: new Error(`Chapter ${event.chapterId} is not loaded`),
						});
						break;
					}
					dispatch(chapterDM.destroy());
					break;
				}
				case "loadLabelData": {
					const chapterDM = novelDM.getChapterDM(event.chapterId);
					if (!chapterDM) {
						raiseTriggerEvent(novelDM.getters, {
							eventType: "errorOccured",
							from: "dataManager",
							error: new Error(`Chapter ${event.chapterId} is not loaded`),
						});
						break;
					}
					dispatch(chapterDM.reloadGroup(event.labelGroupId, true));
					break;
				}
			}

			void Effect.runPromise(requestManager.debounce());
		};

		const start = (): void => {
			running = true;
			timer = setInterval(() => {
				dispatch(novelDM.flush());
				void Effect.runPromise(requestManager.start());
			}, 1500);
		};

		const stop = async (): Promise<void> => {
			running = false;
			if (timer !== null) {
				clearInterval(timer);
				timer = null;
			}
			await Effect.runPromise(requestManager.waitFlush());
		};

		return {
			handleUserEvent,
			getters: novelDM.getters,
			subscribe,
			start,
			stop,
		};
	});
