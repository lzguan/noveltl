import { useCallback, useState } from "react";
import { Effect } from "effect";
import { UnknownError } from "effect/Cause";
import type { NovelGetters, TriggerEvent } from "../controller/types/controllerTypes";
import type { CCProvId, CProvId } from "../controller/types/idTypes";

export function useOpenChapterContents() {
	const [openChapterContentIds, setOpenChapterContentIds] = useState<
		ReadonlyMap<string, string | null>
	>(() => new Map());

	const setContentId = useCallback(
		(chapterServId: string, chapterContentServId: string | null) => {
			setOpenChapterContentIds((prev) => {
				if (prev.has(chapterServId) && prev.get(chapterServId) === chapterContentServId) {
					return prev;
				}
				const next = new Map(prev);
				next.set(chapterServId, chapterContentServId);
				return next;
			});
		},
		[],
	);

	const removeChapter = useCallback((chapterServId: string) => {
		setOpenChapterContentIds((prev) => {
			if (!prev.has(chapterServId)) return prev;
			const next = new Map(prev);
			next.delete(chapterServId);
			return next;
		});
	}, []);

	return {
		openChapterContentIds,
		setContentId,
		removeChapter,
	};
}

export function createOpenChapterContentsSubscriber({
	setContentId,
	removeChapter,
}: Pick<ReturnType<typeof useOpenChapterContents>, "setContentId" | "removeChapter">) {
	const invalidatedContentIds = new Map<CProvId, CCProvId>();

	return function handleControllerEvent(
		getters: NovelGetters,
		event: TriggerEvent,
	): Effect.Effect<void> {
		return Effect.gen(function* () {
			switch (event.eventType) {
				case "chapterOpened": {
					const chapterServId = yield* getters.chapterServerId(event.chapterId);
					if (chapterServId === null) break;
					const chapterSlot = yield* getters
						.chapterGetterSlot(event.chapterId)
						.pipe(Effect.mapError((err) => new UnknownError({ orig: err })));
					if (chapterSlot.status !== "ready") break;
					const chapterContentId =
						yield* chapterSlot.data.chapterGetters.chapterContentId();
					const invalidated =
						invalidatedContentIds.get(event.chapterId) === chapterContentId;
					if (!invalidated) invalidatedContentIds.delete(event.chapterId);
					const ccServId =
						!invalidated && chapterSlot.data.chapterGetters.isTextSynced()
							? yield* getters.chapterContentServerId(event.chapterId)
							: null;
					setContentId(chapterServId, ccServId);
					break;
				}

				case "chapterClosed": {
					invalidatedContentIds.delete(event.chapterId);
					const chapterServId = yield* getters.chapterServerId(event.chapterId);
					if (chapterServId !== null) {
						removeChapter(chapterServId);
					}
					break;
				}

				case "textChanged": {
					const chapterServId = yield* getters.chapterServerId(event.chapterId);
					if (chapterServId !== null) {
						setContentId(chapterServId, null);
					}
					const chapterSlot = yield* getters
						.chapterGetterSlot(event.chapterId)
						.pipe(Effect.mapError((err) => new UnknownError({ orig: err })));
					if (chapterSlot.status === "ready") {
						invalidatedContentIds.set(
							event.chapterId,
							yield* chapterSlot.data.chapterGetters.chapterContentId(),
						);
					}
					break;
				}
			}
		}).pipe(
			Effect.catch((err) => {
				console.error("Error tracking open chapter contents:", err);
				return Effect.succeed(void 0);
			}),
		);
	};
}
