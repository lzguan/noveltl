import type { IDLabelOp, LabelOp } from "./dataTypes";
import type {
	ALRProvId,
	AProvId,
	CCProvId,
	CProvId,
	LGProvId,
	ProvAutoLabel,
	ProvAutoLabelRun,
	ProvChapter,
	ProvLabelGroup,
} from "./idTypes";
import type { CluenerParams, DoNothingParams, Novel, TextOp } from "@/api/models";
import { Effect } from "effect";
import type { KeyedRequestEvent } from "./requestTypes";
import type { NotFoundException } from "./errors";
import type {
	ChapterGetterSlot,
	LabelDataSlot,
	LabelGroupSlot,
	AutoLabelRunGetterSlot,
} from "./helperTypes";
import type { Role } from "@/api/models/role";
import type { UnknownException } from "effect/Cause";

// Generics

/**
 * Subscriber callback invoked on every trigger event with a fresh state snapshot and the event.
 */
export type SubscriberFn<GettersT, TriggerEventT> = (
	getters: GettersT,
	event: TriggerEventT,
) => Effect.Effect<void>;

/**
 * Base controller interface. Events sent before start() are ignored.
 * Subscribers are keyed by reference — the returned unsubscribe function removes that exact reference.
 */
export interface BaseController<GettersT, UserEventT, TriggerEventT> {
	handleUserEvent: (event: UserEventT) => Effect.Effect<void>;
	getters: GettersT;
	subscribe: (
		subscriberFn: SubscriberFn<GettersT, TriggerEventT>,
		priority?: number,
	) => () => void;
}

/**
 * Interface for exposed getters on a chapter data manager. Barebones for now.
 */
export interface ChapterGetters {
	text: () => Effect.Effect<string>;
	chapterContentId: () => Effect.Effect<CCProvId>;
	labelDataSlot: (labelGroupId: LGProvId) => Effect.Effect<LabelDataSlot, NotFoundException>;
}

/**
 * Interface for exposed getters on a novel data manager (and controller). Barebones for now.
 */
export interface NovelGetters {
	novel: () => Effect.Effect<Novel>;
	role: () => Effect.Effect<Role>;
	labelGroupIds: () => Effect.Effect<readonly LGProvId[]>;
	chapterIds: () => Effect.Effect<readonly CProvId[]>;
	chapterGetterSlot: (chapterId: CProvId) => Effect.Effect<ChapterGetterSlot, NotFoundException>;
	labelGroupSlot: (labelGroupId: LGProvId) => Effect.Effect<LabelGroupSlot, NotFoundException>;
	autoLabelRunIds: () => Effect.Effect<readonly ALRProvId[]>;
	autoLabelRunSlot: (
		runId: ALRProvId,
	) => Effect.Effect<AutoLabelRunGetterSlot, NotFoundException>;
}

export type ChapterFilter = {
	readonly start?: number;
	readonly end?: number;
	readonly isPublic?: boolean;
};

/**
 * Type for any event triggered by the user which requires state updates. Will be updated.
 * - `textOp`: inserting/deleting text.
 * - `labelOp`: adding/deleting/updating a label.
 * - `addLabelGroup`: adding a label group.
 * - `loadLabelData`: loading label data for a chapter and label group.
 * - `openChapter`: opening a chapter (loading its content and label data).
 * - `closeChapter`: closing a chapter (destroying the chapter data manager).
 * - `addChapter`: adding a chapter.
 */
export type NovelUserEvent =
	| { eventType: "textOp"; op: TextOp; chapterId: CProvId }
	| { eventType: "labelOp"; op: LabelOp; labelGroupId: LGProvId; chapterId: CProvId }
	| { eventType: "addLabelGroup"; labelGroupName: string }
	| { eventType: "loadLabelData"; labelGroupId: LGProvId; chapterId: CProvId }
	| {
			eventType: "openChapter";
			chapterId: CProvId;
			eagerLabelGroupIds: LGProvId[];
			flags: (
				| {
						now: boolean;
						forEditor: false;
				  }
				| { now: true; forEditor: true }
			) & { fromCached: boolean };
	  }
	| { eventType: "closeChapter"; chapterId: CProvId }
	| {
			eventType: "addChapter";
			chapterNum: number;
			chapterTitle: string;
			chapterIsPublic: boolean;
	  }
	| {
			eventType: "createAutoLabelRun";
			params: CluenerParams | DoNothingParams;
			chapterFilter: ChapterFilter;
	  }
	| { eventType: "refreshAutoLabelRuns" }
	| { eventType: "reloadAutoLabelRun"; runId: ALRProvId }
	| { eventType: "loadAutoLabelData"; autoLabelId: AProvId }
	| {
			eventType: "promoteAutoLabelRun";
			runId: ALRProvId;
			chapterFilter: ChapterFilter;
			labelGroupId: LGProvId;
	  };

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
 * - `errorOccured`: when an error occurs. Two variants:
 * 	- from request manager: batched errors from a single processing cycle (multiple requests can fail in one pass).
 * 	- from data manager: a single action failed (e.g., invalid operation, chapter not loaded).
 */
export type TriggerEvent =
	| { eventType: "textChanged"; op: TextOp; chapterId: CProvId }
	| { eventType: "labelChanged"; op: IDLabelOp }
	| { eventType: "labelGroupAdded"; labelGroup: ProvLabelGroup }
	| { eventType: "chapterAdded"; chapter: ProvChapter }
	| {
			eventType: "errorOccured";
			from: "requestManager";
			data: { error: Error; request: KeyedRequestEvent }[];
	  }
	| { eventType: "errorOccured"; from: "dataManager"; error: Error }
	| { eventType: "chapterOpened"; chapterId: CProvId; flags: { forEditor: boolean } }
	| { eventType: "labelDataReloading"; chapterId: CProvId; labelGroupId: LGProvId }
	| {
			eventType: "labelDataLoaded";
			chapterId: CProvId;
			labelGroupId: LGProvId;
			wasDeleted: boolean;
	  }
	| {
			eventType: "autoLabelRunCreated";
			run: ProvAutoLabelRun;
			autoLabels: Omit<ProvAutoLabel, "autoLabelData">[];
	  }
	| {
			eventType: "autoLabelRunPromoted";
			runId: ALRProvId;
			labelGroupId: LGProvId;
			chapterFilter: ChapterFilter;
			success: readonly {
				chapterId: CProvId;
				chapterContentId: CCProvId;
			}[];
			errors: readonly {
				chapterId: CProvId;
				chapterContentId: CCProvId;
				error: string;
			}[];
	  }
	| { eventType: "autoLabelRunsRefreshed" }
	| { eventType: "autoLabelRunReloaded"; runId: ALRProvId }
	| { eventType: "autoLabelDataLoaded"; autoLabelId: AProvId };

/**
 * Novel-level controller. Events are ignored until start() is called.
 * stop() drains pending requests; after it resolves, handleUserEvent is a no-op.
 * start() should not be called after stop().
 */
export interface NovelController extends BaseController<
	NovelGetters,
	NovelUserEvent,
	TriggerEvent
> {
	/**
	 * Use Effect.runPromise to run the returned effect.
	 */
	start: () => Effect.Effect<void, UnknownException>;
	/**
	 * Use Effect.runPromise to run the returned promise.
	 */
	stop: () => Effect.Effect<void, UnknownException>;
}
