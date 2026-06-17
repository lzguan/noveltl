import type { LabelOp } from "./dataTypes";
import type { ProvChapter, ProvChapterContent, ProvId, ProvLabelGroup } from "./idTypes";
import type { TextOp } from "@/api/models";
import { Effect } from "effect";
import type { KeyedRequestEvent } from "./requestTypes";
import type { LabelDataSlot } from "../dmHelpers";

// Generics

/**
 * Function that takes a set of getters and a trigger event, and performs its own actions.
 */
export type SubscriberFn<GettersT, TriggerEventT> = (
	getters: GettersT,
	event: TriggerEventT,
) => Effect.Effect<void>;

/**
 * Interface for controllers.
 */
export interface BaseController<GettersT, UserEventT, TriggerEventT> {
	/**
	 * Handle an external event, such as a user action.
	 */
	handleUserEvent: (event: UserEventT) => void;
	/**
	 * Get internal data.
	 */
	getters: GettersT;
	/**
	 * Subscribe to trigger events, which are emitted when internal state changes or when certain actions occur.
	 */
	subscribe: (subscriberFn: SubscriberFn<GettersT, TriggerEventT>) => () => void; // returns an unsubscribe function
}

/**
 * Interface for exposed getters on a chapter controller. Not finalized.
 */
export interface ChapterGetters {
	/**
	 * Get the content of this chapter.
	 */
	content: () => ProvChapterContent;
	labelGroup: (labelGroupId: ProvId) => LabelDataSlot | null;
}

/**
 * Interface for exposed getters on a novel controller. Not finalized.
 */
export interface NovelGetters {
	/**
	 * Get novel id.
	 */
	id: () => ProvId;
	/**
	 * Get list of label groups in this novel.
	 */
	labelGroups: () => readonly ProvLabelGroup[];
	/**
	 * Get list of chapters in this novel.
	 */
	chapters: () => readonly ProvChapter[];
	/**
	 * Get a given chapter for this novel.
	 */
	chapter: (
		chapterId: ProvId,
	) =>
		| (ChapterGetters & { status: "loaded" })
		| { status: "notLoaded" | "loading" | "loadError" }
		| null;
}

/**
 * Type for any event triggered by the user which requires state updates. Will be updated.
 * - `textOp`: inserting/deleting text.
 * - `labelOp`: adding/deleting/updating a label.
 * - `addLabelGroup`: adding a label group.
 * - `loadLabelData`: loading label data for a chapter and label group.
 * - `openChapter`: opening a chapter (loading its content and label data).
 * - `closeChapter`: closing a chapter (unloading its content and label data).
 * - `addChapter`: adding a chapter.
 */
export type NovelUserEvent =
	| { eventType: "textOp"; op: TextOp; chapterId: ProvId }
	| { eventType: "labelOp"; op: LabelOp; labelGroupId: ProvId; chapterId: ProvId }
	| { eventType: "addLabelGroup"; labelGroupName: string }
	| { eventType: "loadLabelData"; labelGroupId: ProvId; chapterId: ProvId }
	| { eventType: "openChapter"; chapterId: ProvId }
	| { eventType: "closeChapter"; chapterId: ProvId }
	| { eventType: "addChapter"; chapterNum: number; chapterTitle: string; chapterIsPublic: boolean };

/**
 * Type for any event triggered by the controller due to state change or completion of an action, which may be subscribed to. Will be updated.
 * There are three main categories of trigger events:
 * - State change: when state of controller successfully changes internally before backend sync.
 * - Backend sync completion: when a request to the backend successfully completes and the controller updates its state accordingly.
 * - Error: when a request to the backend fails after all retries, or encounters a fatal error.
 *
 * List of trigger events:
 * - `textChanged`: when text content of a chapter successfully changes.
 * - `labelChanged`: when labels of a chapter successfully change.
 * - `labelGroupAdded`: when a label group is successfully added.
 * - `chapterAdded`: when a chapter is successfully added.
 * - `errorOccured`: when an error occurs. Appears in two variants:
 * 	- from request manager: when a request is raised due to some backend/network issue.
 * 	- from data manager: when a request unsuccessfully completes (for example, due to illegal operations).
 */
export type TriggerEvent =
	| { eventType: "textChanged"; op: TextOp; chapterId: ProvId }
	| { eventType: "labelChanged"; op: LabelOp; labelGroupId: ProvId; chapterId: ProvId }
	| { eventType: "labelGroupAdded"; labelGroup: ProvLabelGroup }
	| { eventType: "chapterAdded"; chapter: ProvChapter }
	| {
			eventType: "errorOccured";
			from: "requestManager";
			data: { error: Error; request: KeyedRequestEvent }[];
	  }
	| { eventType: "chapterOpened"; chapterId: ProvId };

export interface NovelController extends BaseController<
	NovelGetters,
	NovelUserEvent,
	TriggerEvent
> {}
