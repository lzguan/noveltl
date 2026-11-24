import { Effect } from "effect";
import { UnknownError } from "effect/Cause";
import type {
	NovelGetters,
	NovelUserEvent,
	TriggerEvent,
} from "../controller/types/controllerTypes";
import type { CCProvId, CCServId, CProvId, LGProvId } from "../controller/types/idTypes";
import type { LoadingPayload } from "../hooks/useEditorState";
import type { useChapters } from "../hooks/useChapters";

export function createChapterManager({
	controllerUserEvent,
	chapters,
	setLoading,
	labelGroupsRef,
}: {
	controllerUserEvent: (event: NovelUserEvent) => void;
	chapters: ReturnType<typeof useChapters>;
	setLoading: (val: LoadingPayload) => void;
	labelGroupsRef: { current: Map<LGProvId, unknown> };
}) {
	const invalidatedContentIds = new Map<CProvId, CCProvId>();

	function handleControllerEvent(
		getters: NovelGetters,
		event: TriggerEvent,
	): Effect.Effect<void> {
		return Effect.gen(function* () {
			if (event.eventType === "chapterAdded") {
				chapters.addChapter(event.chapter);
			} else if (event.eventType === "chapterOpened") {
				if (chapters.tabsRef.current.some((tab) => tab.chapterId === event.chapterId)) {
					chapters.updateTabs(
						chapters.tabsRef.current.map((tab) =>
							tab.chapterId === event.chapterId ? { ...tab, status: "ready" } : tab,
						),
					);
				}
				const chapterServId = yield* getters.chapterServerId(event.chapterId);
				if (chapterServId !== null) {
					const chapterSlot = yield* getters
						.chapterGetterSlot(event.chapterId)
						.pipe(Effect.mapError((err) => new UnknownError({ orig: err })));
					if (chapterSlot.status === "ready") {
						const chapterContentId =
							yield* chapterSlot.data.chapterGetters.chapterContentId();
						const invalidated =
							invalidatedContentIds.get(event.chapterId) === chapterContentId;
						if (!invalidated) invalidatedContentIds.delete(event.chapterId);
						const ccServId =
							!invalidated && chapterSlot.data.chapterGetters.isTextSynced()
								? yield* getters.chapterContentServerId(event.chapterId)
								: null;
						chapters.setOpenChapterContentId(chapterServId, ccServId);
					}
				}
			} else if (event.eventType === "chapterClosed") {
				invalidatedContentIds.delete(event.chapterId);
				const chapterServId = yield* getters.chapterServerId(event.chapterId);
				if (chapterServId !== null) {
					chapters.removeOpenChapterContentId(chapterServId);
				}
				chapters.closingChapterIdsRef.current.delete(event.chapterId);
				if (chapters.tabsRef.current.some((tab) => tab.chapterId === event.chapterId)) {
					openChapter(event.chapterId);
				}
			} else if (event.eventType === "textChanged") {
				const chapterServId = yield* getters.chapterServerId(event.chapterId);
				if (chapterServId !== null) {
					chapters.setOpenChapterContentId(chapterServId, null);
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
			} else if (event.eventType === "chapterOpenFailed") {
				const result = chapters.removeTab(event.chapterId);
				if (result?.wasActive) switchChapter(result.nextChapterId);
			}
		}).pipe(
			Effect.catch((err) => {
				console.error("Error in chapter manager:", err);
				return Effect.succeed(void 0);
			}),
		);
	}

	function openChapter(
		chapterId: CProvId,
		highlight?: { start: number; end: number; desiredCCId?: CCServId },
	) {
		if (chapters.activeChapterIdRef.current === chapterId) {
			setLoading({ loading: true, empty: false });
		}
		controllerUserEvent({
			eventType: "openChapter",
			chapterId,
			eagerLabelGroupIds: Array.from(labelGroupsRef.current.keys()),
			flags: { now: true, forEditor: true, fromCached: true, highlight },
		});
	}

	function switchChapter(
		chapterId: CProvId | null,
		highlight?: { start: number; end: number; desiredCCId?: CCServId },
	) {
		if (chapterId === null) {
			setLoading({ empty: true });
			return;
		}
		setLoading({ loading: true, empty: false });
		const existing = chapters.tabsRef.current.find((tab) => tab.chapterId === chapterId);
		if (!existing) {
			chapters.updateTabs([...chapters.tabsRef.current, { chapterId, status: "loading" }]);
		}
		chapters.updateActive(chapterId);
		if (chapters.closingChapterIdsRef.current.has(chapterId)) {
			return;
		}
		if (existing?.status === "loading") return;
		openChapter(chapterId, highlight);
	}

	function closeChapter(chapterId: CProvId) {
		const result = chapters.removeTab(chapterId);
		if (result === null) return;

		if (!chapters.closingChapterIdsRef.current.has(chapterId)) {
			chapters.closingChapterIdsRef.current.add(chapterId);
			controllerUserEvent({
				eventType: "closeChapter",
				chapterId,
			});
		}
		if (result.wasActive) switchChapter(result.nextChapterId);
	}

	function addChapter(chapterNum: number, chapterTitle: string, chapterIsPublic: boolean) {
		controllerUserEvent({
			eventType: "addChapter",
			chapterNum,
			chapterTitle,
			chapterIsPublic,
		});
	}

	return { handleControllerEvent, switchChapter, closeChapter, addChapter };
}
