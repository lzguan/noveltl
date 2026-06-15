import type { LabelDataEntry, LabelOp } from "./dataTypes";
import type { ProvId } from "./idTypes";
import type { Prov } from "./helperTypes";
import type { Chapter, ChapterContent, LabelGroup, TextOp } from "@/api/models";
import { Effect } from "effect";
import type { KeyedRequestEvent } from "./requestTypes";

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
	handleUserEvent: (event: UserEventT) => void;
	getters: GettersT;
	subscribe: (subscriberFn: SubscriberFn<GettersT, TriggerEventT>) => () => void; // returns an unsubscribe function
}

export interface ControllerRuntime<GettersT, UserEventT, TriggerEventT> {
	controller: BaseController<GettersT, UserEventT, TriggerEventT>;
}

export interface ChapterGetters {
	content: () => Prov<ChapterContent>;
	labelGroup: (labelGroupId: ProvId) => LabelDataEntry | null;
}

export interface NovelGetters {
	id: () => ProvId;
	labelGroups: () => readonly Prov<LabelGroup>[];
	chapters: () => readonly Prov<Chapter>[];
	chapter: (
		chapterId: ProvId,
	) =>
		| (ChapterGetters & { status: "loaded" })
		| { status: "notLoaded" | "loading" | "loadError" }
		| null;
}

/**
 * Anything that requires backend sync.
 */
export type NovelUserEvent =
	| { eventType: "textOp"; op: TextOp; chapterId: ProvId }
	| { eventType: "labelOp"; op: LabelOp; labelGroupId: ProvId; chapterId: ProvId }
	| { eventType: "addLabelGroup"; labelGroupName: string }
	| { eventType: "loadLabelData"; labelGroupId: ProvId; chapterId: ProvId }
	| { eventType: "openChapter"; chapterId: ProvId }
	| { eventType: "closeChapter"; chapterId: ProvId }
	| { eventType: "addChapter"; chapterNum: number; chapterTitle: string; chapterIsPublic: boolean };

export type ChapterUserEvent =
	| { eventType: "textOp"; op: TextOp }
	| { eventType: "labelOp"; op: LabelOp; labelGroupId: ProvId }
	| { eventType: "loadLabelData"; labelGroupId: ProvId };

export type TriggerEvent =
	| { eventType: "textChanged"; op: TextOp; chapterId: ProvId }
	| { eventType: "labelChanged"; op: LabelOp; labelGroupId: ProvId; chapterId: ProvId }
	| { eventType: "labelGroupAdded"; labelGroup: LabelGroup }
	| {
			eventType: "errorOccured";
			from: "requestManager";
			data: { error: Error; request: KeyedRequestEvent }[];
	  };

export interface NovelController extends BaseController<
	NovelGetters,
	NovelUserEvent,
	TriggerEvent
> {}

export interface ChapterController extends BaseController<
	ChapterGetters,
	ChapterUserEvent,
	TriggerEvent
> {}
