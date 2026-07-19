import { Effect } from "effect";
import type {
	NovelGetters,
	NovelUserEvent,
	TriggerEvent,
} from "../controller/types/controllerTypes";
import type { CProvId, LGProvId } from "../controller/types/idTypes";
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
	function handleControllerEvent(
		_getters: NovelGetters,
		event: TriggerEvent,
	): Effect.Effect<void> {
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
		} else if (event.eventType === "chapterClosed") {
			chapters.closingChapterIdsRef.current.delete(event.chapterId);
			if (chapters.tabsRef.current.some((tab) => tab.chapterId === event.chapterId)) {
				openChapter(event.chapterId);
			}
		} else if (event.eventType === "chapterOpenFailed") {
			const result = chapters.removeTab(event.chapterId);
			if (result?.wasActive) switchChapter(result.nextChapterId);
		}
		return Effect.succeed(void 0);
	}

	function openChapter(chapterId: CProvId) {
		if (chapters.activeChapterIdRef.current === chapterId) {
			setLoading({ loading: true, empty: false });
		}
		controllerUserEvent({
			eventType: "openChapter",
			chapterId,
			eagerLabelGroupIds: Array.from(labelGroupsRef.current.keys()),
			flags: { now: true, forEditor: true, fromCached: true },
		});
	}

	function switchChapter(chapterId: CProvId | null) {
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
		openChapter(chapterId);
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
