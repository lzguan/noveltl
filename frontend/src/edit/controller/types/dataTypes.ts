import type { CProvId, LGProvId, ProvChapter, ProvLabelGroup, ServId } from "./idTypes";
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
			chapterId: CProvId,
			eager: LGProvId[],
			now: boolean,
		) => Effect.Effect<
			RequestEvent[],
			NotFoundException | LoadingException | AlreadyOpenException | UnknownException
		>;
		/**
		 * Flush any passive request events.
		 */
		flush: () => Effect.Effect<RequestEvent[], UnknownException>;
		/**
		 * Get the chapter data manager for a given chapter, or null if not loaded.
		 */
		getChapterDM: (chapterId: CProvId) => ChapterDataManager | null;
	},
	{
		id: () => ServId;
		labelGroups: () => readonly ProvLabelGroup[];
		chapters: () => readonly ProvChapter[];
	}
>;

/**
 * Holds data associated to a single chapter. Specifically, holds the following data:
 * - The content of the chapter.
 * - The labels associated to this chapter, organized by label group.
 */
export type ChapterDataManager = DataManager<
	{
		/**
		 * Add a label to a given label group for this chapter. Raises a trigger event with the new label's ProvId on success. Throws an error if one of the following occurs:
		 * - The labels associated with the given label group is not loaded.
		 * - The new label overlaps with an existing label.
		 *
		 * Returns any auto-flushed request events from a previous op type (e.g., pending text ops flushed when switching to label ops).
		 */
		addLabel: (
			labelGroupId: LGProvId,
			startPos: number,
			endPos: number,
			word: string,
			entityGroup?: string,
			score?: number,
			dirty?: boolean,
		) => Effect.Effect<RequestEvent[], UnknownException>;
		/**
		 * Delete a label from a given chapter and label group. Raises a trigger event on success. Throws an error if one of the following occurs:
		 * - The labels associated with the given label group is not loaded.
		 * - The label to be deleted does not exist.
		 *
		 * Returns any auto-flushed request events from a previous op type.
		 */
		deleteLabel: (
			labelGroupId: LGProvId,
			startPos: number,
			endPos: number,
		) => Effect.Effect<RequestEvent[], UnknownException>;
		/**
		 * Update a label in a given chapter and label group, keyed by the label group id, start position, and end position. Raises a trigger event on success. Throws an error if one of the following occurs:
		 * - The labels associated with the given label group is not loaded.
		 * - The label to be updated does not exist.
		 *
		 * Returns any auto-flushed request events from a previous op type.
		 */
		updateLabel: (
			labelGroupId: LGProvId,
			startPos: number,
			endPos: number,
			newStartPos?: number | null,
			newEndPos?: number | null,
			newWord?: string | null,
			entityGroup?: string,
			score?: number,
			dirty?: boolean,
		) => Effect.Effect<RequestEvent[], UnknownException>;
		/**
		 * Insert text at a given position in the chapter content. Raises a trigger event on success. Throws an error if the position is invalid.
		 *
		 * Returns any auto-flushed request events from a previous op type (e.g., pending label ops flushed when switching to text ops).
		 */
		insertTextAt: (pos: number, text: string) => Effect.Effect<RequestEvent[], UnknownException>;
		/**
		 * Delete text in a given range in the chapter content. Raises a trigger event on success. Throws an error if the range is invalid.
		 *
		 * Returns any auto-flushed request events from a previous op type.
		 */
		deleteTextAt: (
			startPos: number,
			endPos: number,
		) => Effect.Effect<RequestEvent[], UnknownException>;
		/**
		 * Flush any passive request events from the current op queue.
		 */
		flush: () => Effect.Effect<RequestEvent[], UnknownException>;
		/**
		 * Reload label data and labels for a given label group from the server. Passive request (read-only). If now is true, immediately flushes the dispatcher queue to dispatch the event; otherwise it remains queued until an active event or explicit flush triggers it.
		 */
		reloadGroup(
			labelGroupId: LGProvId,
			now: boolean,
		): Effect.Effect<RequestEvent[], UnknownException>;
		/**
		 * Cleans up internal state when the chapter is closed. Makes all other actions invalid after this is called. Throws an error if the chapter is already closed. Returns empty list (pending passive events are discarded).
		 */
		destroy: () => Effect.Effect<RequestEvent[], UnknownException>;
	},
	{}
>;
