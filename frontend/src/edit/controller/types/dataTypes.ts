import type { ProvId } from "./idTypes";
import type { RequestEvent } from "./requestTypes";
import type { Prov } from "./helperTypes";
import type {
	AddLabelOp,
	Chapter,
	DeleteLabelOp,
	Label,
	LabelData,
	LabelGroup,
	UpdateLabelOp,
} from "@/api/models";
import type { Effect } from "effect";
import type { ChapterController } from "./controllerTypes";

export type LabelOp = AddLabelOp | DeleteLabelOp | UpdateLabelOp;

export type UnsyncedLoadingStatus =
	| "notLoaded"
	| "loading"
	| "loadError"
	| "notCreated"
	| "creating";

export type LoadingStatus = UnsyncedLoadingStatus | "loaded";

export type LabelDataEntry =
	| { status: UnsyncedLoadingStatus }
	| {
			status: "loaded";
			labelData: Prov<LabelData>;
			labels: Prov<Label>[]; // sorted by start position
	  };

type _ChapterControllerEntry =
	| { status: UnsyncedLoadingStatus }
	| { status: "loaded"; controller: ChapterController };

export type ChapterControllerEntry = _ChapterControllerEntry & { chapter: Prov<Chapter> };

export type NovelDataManager = {
	addLabelGroup: (labelGroupName: string) => Effect.Effect<RequestEvent[]>;
	addChapter: (
		chapterNum: number,
		chapterTitle: string,
		chapterIsPublic: boolean,
	) => Effect.Effect<RequestEvent[], Error>;
	openChapter: (
		chapterId: ProvId,
		getMyState: () => LoadingStatus,
		setMyState: (state: ChapterControllerEntry) => void,
	) => Effect.Effect<RequestEvent[], Error>;

	getters: {
		getGroups: () => readonly Prov<LabelGroup>[];
		getChapters: () => readonly Prov<Chapter>[];
	};
};

export type ChapterDataManager = {
	addLabel: (
		labelGroupId: string,
		labelDataId: string,
		startPos: number,
		endPos: number,
		word: string,
		entityGroup?: string,
		score?: number,
		dirty?: boolean,
	) => Effect.Effect<ProvId, Error>;
	deleteLabel: (
		labelGroupId: string,
		labelDataId: string,
		startPos: number,
		endPos: number,
	) => Effect.Effect<ProvId, Error>;
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
	) => Effect.Effect<ProvId, Error>;
	insertTextAt: (pos: number, text: string) => Effect.Effect<void, Error>;
	deleteTextAt: (startPos: number, endPos: number) => Effect.Effect<void, Error>;

	flush: () => Effect.Effect<RequestEvent[]>;

	reloadGroup(labelGroupId: string): Effect.Effect<RequestEvent[]>;

	destroy: () => Effect.Effect<RequestEvent[]>;
};
