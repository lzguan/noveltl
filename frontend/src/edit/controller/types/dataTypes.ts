import type { ProvId } from "./idTypes";
import type { RequestEvent } from "./requestTypes";
import type { AddLabelOp, DeleteLabelOp, UpdateLabelOp } from "@/api/models";
import type { Effect } from "effect";
import type { UnknownException } from "effect/Cause";
import type {
	AlreadyOpenException,
	DuplicateChapterNumException,
	LoadingException,
	NotFoundException,
} from "./errors";

export type LabelOp = AddLabelOp | DeleteLabelOp | UpdateLabelOp;
/**
 * A data manager is a data structure that maintains the state of some defined data. It provides a set of actions that can be performed on the data and a set of getters to retrieve the data. The intended use of a data manager is to manage the internal state of the application and provide a clear interface for performing operations on the data and retrieving the data, while abstracting away the details of how the data is stored and updated.
 *
 * An action is a function that immediately performs some synchronous operations on the data, then returns a list of request events that are called asyncronously at a later time. The request events are responsible for the following:
 * - Syncing changes to the backend via network requests.
 * - Updating the internal state of the data manager based on the response from the backend.
 * - Emitting trigger events corresponding to the completion of the action.
 * - Ensuring internal state is consistent after backend errors.
 *
 * This type is mainly to clarify the intended use of the data manager pattern.
 */
type DataManager<ActionsT, GettersT> = ActionsT & {
	getters: GettersT;
};

/**
 * Holds data associated to an entire novel. Specifically, holds the following data:
 * - The list of label groups in the novel.
 * - The list of chapters in the novel.
 * - Any open chapter data through the chapter data manager interface.
 */
export type NovelDataManager = DataManager<
	{
		/**
		 * Add a label group to the novel.
		 */
		addLabelGroup: (labelGroupName: string) => Effect.Effect<RequestEvent[], UnknownException>;
		/**
		 * Add a new chapter to the novel. Throws an error if chapterNum is not unique.
		 */
		addChapter: (
			chapterNum: number,
			chapterTitle: string,
			chapterIsPublic: boolean,
		) => Effect.Effect<RequestEvent[], UnknownException | DuplicateChapterNumException>;
		/**
		 * Load all data associated to a given chapter along with the required interfaces for data interaction and retrieval. Throws an error if chapter is already loaded. Lazy loads if now is false, and loads immediately if now is true.
		 */
		openChapter: (
			chapterId: ProvId,
			eager: ProvId[],
			now: boolean,
		) => Effect.Effect<
			RequestEvent[],
			NotFoundException | LoadingException | AlreadyOpenException | UnknownException
		>;
		/**
		 * Flush any passive request events.
		 */
		flush: () => Effect.Effect<RequestEvent[]>;
	},
	{}
>;

/**
 * Holds data associated to a single chapter. Specifically, holds the following data:
 * - The content of the chapter.
 * - The labels associated to this chapter, organized by label group.
 */
export type ChapterDataManager = DataManager<
	{
		/**
		 * Add a label to a given label group for this chapter. Throws an error if one of the following occurs:
		 * - The labels associated with the given label group is not loaded.
		 * - The new label overlaps with an existing label.
		 */
		addLabel: (
			labelGroupId: string,
			labelDataId: string,
			startPos: number,
			endPos: number,
			word: string,
			entityGroup?: string,
			score?: number,
			dirty?: boolean,
		) => Effect.Effect<ProvId, UnknownException>;
		/**
		 * Delete a label from a given chapter and label group. Throws an error if one of the following occurs:
		 * - The labels associated with the given label group is not loaded.
		 * - The label to be deleted does not exist.
		 */
		deleteLabel: (
			labelGroupId: string,
			labelDataId: string,
			startPos: number,
			endPos: number,
		) => Effect.Effect<ProvId, UnknownException>;
		/**
		 * Update a label in a given chapter and label group, keyed by the label group id, start position, and end position. Throws an error if one of the following occurs:
		 * - The labels associated with the given label group is not loaded.
		 * - The label to be updated does not exist.
		 */
		updateLabel: (
			labelGroupId: string,
			labelDataId: string,
			startPos: number,
			endPos: number,
			newStartPos?: number | null,
			newEndPos?: number | null,
			newWord?: string | null,
			entityGroup?: string,
			score?: number,
			dirty?: boolean,
		) => Effect.Effect<ProvId, UnknownException>;
		/**
		 * Insert text at a given position in the chapter content. Throws an error if the position is invalid.
		 */
		insertTextAt: (pos: number, text: string) => Effect.Effect<void, UnknownException>;
		/**
		 * Delete text in a given range in the chapter content. Throws an error if the range is invalid.
		 */
		deleteTextAt: (startPos: number, endPos: number) => Effect.Effect<void, UnknownException>;
		/**
		 * Flush any passive request events.
		 */
		flush: () => Effect.Effect<RequestEvent[]>;
		/**
		 * Load or reload a given label data for this chapter corresponding to a given label group.
		 */
		reloadGroup(labelGroupId: string): Effect.Effect<RequestEvent[]>;
		/**
		 * Cleans up internal state and emits necessary request events when the chapter is closed. Makes all other actions invalid after this is called. Throws an error if the chapter is already closed.
		 */
		destroy: () => Effect.Effect<RequestEvent[]>;
	},
	{}
>;
