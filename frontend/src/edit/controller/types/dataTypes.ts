import type { CProvId, LGProvId, LProvId, ALRProvId, AProvId } from "./idTypes";
import type { RequestEvent } from "./requestTypes";
import type { AddLabelOp, DeleteLabelOp, UpdateLabelOp } from "@/api/models";
import type { Effect } from "effect";
import type { UnknownException } from "effect/Cause";
import type {
	AlreadyOpenException,
	DuplicateChapterNumException,
	FatalException,
	LoadingException,
	NotFoundException,
} from "./errors";
import type { ChapterGetters, ChapterFilter } from "./controllerTypes";
import type { NovelGetters } from "./controllerTypes";
import type { AutoLabelRunGetterSlot } from "./helperTypes";
import type { CluenerParams, DoNothingParams } from "@/api/models";

export type LabelOp = AddLabelOp | DeleteLabelOp | UpdateLabelOp;

export type IDLabelOp = LabelOp & { labelId: LProvId; labelGroupId: LGProvId; chapterId: CProvId };
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
 * Manages novel-level state: label groups, chapters, and open chapter data managers.
 */
export type NovelDataManager = DataManager<
	{
		/**
		 * @param labelGroupName - Display name for the new group. Backend enforces max 31 chars; frontend validation TODO.
		 */
		addLabelGroup: (labelGroupName: string) => Effect.Effect<RequestEvent[], UnknownException>;
		/**
		 * @param chapterNum - Must be unique across the novel.
		 * @param chapterTitle - Display title.
		 * @param chapterIsPublic - Visibility flag.
		 */
		addChapter: (
			chapterNum: number,
			chapterTitle: string,
			chapterIsPublic: boolean,
		) => Effect.Effect<RequestEvent[], UnknownException | DuplicateChapterNumException>;

		/**
		 * Loads chapter data from server. On success, the chapter becomes accessible via getChapterDM().
		 * @param chapterId - Chapter to open.
		 * @param eager - Label groups whose labels should be fetched immediately (others are lazy-loaded on demand via reloadGroup).
		 * @param now - If true, dispatches immediately. If false, deferred until the next flush or mutating action.
		 * @param flags - Additional flags for opening chapter. Follows the following rules:
		 * - The `forEditor` flag indicates whether the chapter is being opened for the editor (as opposed to a background operation like preloading). If true, will simply emit the forEditor flag in the trigger event.
		 * - The `fromCached` flag indicates whether the chapter data is being loaded from a cached state on the backend. If true, the controller will attempt to use cached data on the frontend for the chapter if available, and will emit the fromCached flag in the trigger event. If false, the controller will throw an error if the chapter data is already cached on the frontend. (these semantics are not so good, rethink this sometime)
		 * - The `now` flag indicates whether the request events for opening the chapter should be dispatched immediately or deferred until the next flush or mutating action.
		 */
		openChapter: (
			chapterId: CProvId,
			eager: LGProvId[],
			flags: ({ now: boolean; forEditor: false } | { now: true; forEditor: true }) & {
				fromCached: boolean;
			},
		) => Effect.Effect<
			RequestEvent[],
			NotFoundException | LoadingException | AlreadyOpenException | UnknownException
		>;
		/**
		 * Returns any deferred passive request events that have been queued but not yet dispatched.
		 */
		flush: () => Effect.Effect<RequestEvent[], UnknownException>;
		/**
		 * @param chapterId - Returns null if chapter is not open or still loading.
		 */
		getChapterDM: (chapterId: CProvId) => ChapterDataManager | null;
		/**
		 * Creates an autolabel run and dispatches workers.
		 */
		createAutoLabelRun: (
			params: CluenerParams | DoNothingParams,
			chapterFilter: ChapterFilter,
		) => Effect.Effect<RequestEvent[], UnknownException | FatalException>;
		/**
		 * Promotes autolabel results from a run into a label group.
		 * Locks both the run and the label group to prevent concurrent modification.
		 */
		promoteAutoLabelRun: (
			runId: ALRProvId,
			labelGroupId: LGProvId,
			chapterFilter: ChapterFilter,
		) => Effect.Effect<RequestEvent[], UnknownException | FatalException>;
		/**
		 * Reloads the autolabel run list from the server and replaces the local index.
		 */
		refreshAutoLabelRuns: (flags?: {
			now: boolean;
		}) => Effect.Effect<RequestEvent[], UnknownException | FatalException>;
		/**
		 * Reloads autolabel metadata for a single run from the server.
		 */
		reloadAutoLabelRun: (
			runId: ALRProvId,
			flags?: {
				now: boolean;
			},
		) => Effect.Effect<RequestEvent[], UnknownException | FatalException>;
		/**
		 * Loads autolabel data (the label payload) for a single autolabel.
		 */
		loadAutoLabelData: (
			autoLabelId: AProvId,
			flags?: {
				now: boolean;
			},
		) => Effect.Effect<RequestEvent[], UnknownException | FatalException>;
	},
	NovelGetters
>;

/**
 * Getters exposed by the autolabel data manager.
 */
export interface AutolabelGetters {
	autoLabelRunIds: () => Effect.Effect<readonly ALRProvId[]>;
	autoLabelRunSlot: (
		runId: ALRProvId,
	) => Effect.Effect<AutoLabelRunGetterSlot, NotFoundException>;
}

/**
 * Manages autolabel runs and their child autolabels.
 */
export type AutolabelDataManager = DataManager<
	{
		createAutoLabelRun: (
			params: CluenerParams | DoNothingParams,
			chapterFilter: ChapterFilter,
		) => Effect.Effect<RequestEvent[], UnknownException | FatalException>;
		promoteAutoLabelRun: (
			runId: ALRProvId,
			labelGroupId: LGProvId,
			chapterFilter: ChapterFilter,
		) => Effect.Effect<RequestEvent[], UnknownException | FatalException>;
		refreshAutoLabelRuns: (flags?: {
			now: boolean;
		}) => Effect.Effect<RequestEvent[], UnknownException | FatalException>;
		reloadAutoLabelRun: (
			runId: ALRProvId,
			flags?: {
				now: boolean;
			},
		) => Effect.Effect<RequestEvent[], UnknownException | FatalException>;
		loadAutoLabelData: (
			autoLabelId: AProvId,
			flags?: {
				now: boolean;
			},
		) => Effect.Effect<RequestEvent[], UnknownException | FatalException>;
	},
	AutolabelGetters
>;

/**
 * Manages a single chapter's text content and per-label-group labels.
 *
 * Text ops and label ops cannot be batched together. Switching between them
 * (e.g., calling insertTextAt after addLabel) auto-flushes the pending ops
 * from the previous type, returning them as RequestEvents.
 *
 * All actions fail if the chapter has been destroyed via destroy().
 * Getters are a placeholder — will be populated with chapter-level read accessors.
 */
export type ChapterDataManager = DataManager<
	{
		/**
		 * Fails if: label group not loaded, overlap with existing label, bounds invalid, or word doesn't match text at [startPos, endPos).
		 * @param labelGroupId - Target label group.
		 * @param startPos - Inclusive start index in chapter text.
		 * @param endPos - Exclusive end index. Must satisfy startPos < endPos <= text.length.
		 * @param word - Must equal text.slice(startPos, endPos).
		 * @param entityGroup - Optional entity classification.
		 * @param score - Optional confidence score in [0, 1].
		 * @param dirty - Whether this label needs review. Defaults to true.
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
		 * Fails if: label group not loaded, or no label exists at [startPos, endPos).
		 * @param labelGroupId - Target label group.
		 * @param startPos - Exact start of label to delete.
		 * @param endPos - Exact end of label to delete.
		 */
		deleteLabel: (
			labelGroupId: LGProvId,
			startPos: number,
			endPos: number,
		) => Effect.Effect<RequestEvent[], UnknownException>;
		/**
		 * Updates a label keyed by its current [startPos, endPos). Pass null/undefined to keep a field unchanged. If bounds change, newWord is required. Fails if newWord is provided without changing bounds.
		 * Fails if: label group not loaded, label not found, new bounds invalid, or new position overlaps.
		 * @param labelGroupId - Target label group.
		 * @param startPos - Current start of label to update.
		 * @param endPos - Current end of label to update.
		 * @param newStartPos - New start, or null to keep.
		 * @param newEndPos - New end, or null to keep.
		 * @param newWord - Required if bounds change. Must match text at new range.
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
		 * Labels straddling the insertion point are dropped; labels after are shifted. Affects all label groups. No-ops if text is empty.
		 * @param pos - Insertion index. Must satisfy 0 <= pos <= text.length.
		 * @param text - Text to insert.
		 */
		insertTextAt: (
			pos: number,
			text: string,
		) => Effect.Effect<RequestEvent[], UnknownException>;
		/**
		 * Labels overlapping [startPos, endPos) are dropped; labels after are shifted backward. Affects all label groups.
		 * @param startPos - Inclusive start of deletion range.
		 * @param endPos - Exclusive end. Must satisfy 0 <= startPos < endPos <= text.length.
		 */
		deleteTextAt: (
			startPos: number,
			endPos: number,
		) => Effect.Effect<RequestEvent[], UnknownException>;
		/**
		 * Flushes any pending operations into RequestEvents. Returns [] if nothing is pending.
		 */
		flush: () => Effect.Effect<RequestEvent[], UnknownException>;
		/**
		 * Fetches fresh label data + labels from server for a label group. Read-only (does not modify backend state).
		 * @param labelGroupId - Label group to reload.
		 * @param now - If true, dispatches immediately. If false, deferred until the next flush or mutating action.
		 */
		reloadGroup(
			labelGroupId: LGProvId,
			now: boolean,
		): Effect.Effect<RequestEvent[], UnknownException>;
		/**
		 * Marks this chapter DM as destroyed. All subsequent actions will fail. Returns [].
		 */
		destroy: () => Effect.Effect<RequestEvent[], UnknownException>;
	},
	ChapterGetters
>;
