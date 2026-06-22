import { Effect } from "effect";
import type {
	NovelGetters,
	NovelUserEvent,
	TriggerEvent,
} from "../controller/types/controllerTypes";
import type { CProvId, LGProvId } from "../controller/types/idTypes";
import type { LoadingPayload } from "../hooks/useEditorState";
import type { useChapterList } from "../hooks/useChapterList";

export function createChapterManager({
	controllerUserEvent,
	chapterList,
	setLoading,
	labelGroupsRef,
}: {
	controllerUserEvent: (event: NovelUserEvent) => void;
	chapterList: ReturnType<typeof useChapterList>;
	setLoading: (val: LoadingPayload) => void;
	labelGroupsRef: { current: Map<LGProvId, unknown> };
}) {
	function handleControllerEvent(
		_getters: NovelGetters,
		event: TriggerEvent,
	): Effect.Effect<void> {
		if (event.eventType === "chapterAdded") {
			chapterList.addChapter(event.chapter);
		}
		return Effect.succeed(void 0);
	}

	function switchChapter(chapterId: CProvId) {
		setLoading({ loading: true });
		controllerUserEvent({
			eventType: "openChapter",
			chapterId,
			eagerLabelGroupIds: Array.from(labelGroupsRef.current.keys()),
			flags: { now: true, forEditor: true, fromCached: true },
		});
	}

	function addChapter(chapterNum: number, chapterTitle: string, chapterIsPublic: boolean) {
		controllerUserEvent({
			eventType: "addChapter",
			chapterNum,
			chapterTitle,
			chapterIsPublic,
		});
	}

	return { handleControllerEvent, switchChapter, addChapter };
}
