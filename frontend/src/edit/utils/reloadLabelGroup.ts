import { Effect } from "effect";
import type { NovelGetters, NovelUserEvent } from "../controller/types/controllerTypes";
import type { CProvId, LGProvId } from "../controller/types/idTypes";

export function reloadLabelGroupInLoadedChapters({
	getters,
	controllerUserEvent,
	labelGroupId,
	activeChapterId,
}: {
	getters: NovelGetters;
	controllerUserEvent(event: NovelUserEvent): void;
	labelGroupId: LGProvId;
	activeChapterId: CProvId | null;
}): Effect.Effect<void> {
	return Effect.gen(function* () {
		const chapterIds = yield* getters.chapterIds();
		const ordered =
			activeChapterId !== null && chapterIds.includes(activeChapterId)
				? [activeChapterId, ...chapterIds.filter((id) => id !== activeChapterId)]
				: chapterIds;
		for (const chapterId of ordered) {
			const chapterSlot = yield* Effect.result(getters.chapterGetterSlot(chapterId));
			if (chapterSlot._tag === "Failure" || chapterSlot.success.status !== "ready") continue;
			const chapterGetters = chapterSlot.success.data.chapterGetters;
			if (chapterGetters.isDestroyed()) continue;
			const labelDataSlot = yield* Effect.result(chapterGetters.labelDataSlot(labelGroupId));
			if (labelDataSlot._tag === "Failure") continue;
			controllerUserEvent({ eventType: "loadLabelData", labelGroupId, chapterId });
		}
	});
}
