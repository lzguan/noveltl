import type {
	GroupData,
	GroupingResponse,
	GroupValueCount,
	InstanceQueryResult,
	SortKey,
	SortDirection,
	WorkflowResponse,
	WorkflowSummary,
} from "@/api/models";

export type Loadable<T> =
	| { status: "idle" }
	| { status: "loading" }
	| { status: "error"; message: string }
	| { status: "ready"; data: T };

export interface Page<T> {
	items: readonly T[];
	start: number;
	end: number;
	total?: number;
	hasPrevious: boolean;
	hasNext: boolean;
}

export interface ActiveGroupingState {
	grouping: GroupingResponse;
	values: Loadable<Page<GroupValueCount>>;
	selectedValues: readonly GroupData[];
	search: string;
}

export type QueryStatus =
	| { status: "idle" }
	| { status: "submitting" }
	| { status: "error"; message: string };

export interface WorkflowSelectionModel {
	workflows: Loadable<readonly WorkflowSummary[]>;
	searchText: string;
	activeWorkflowId: string | null;
	activeWorkflow: Loadable<WorkflowResponse>;
	setWorkflowSearchText: (searchText: string) => void;
	selectWorkflow: (workflowId: string) => void;
}

export interface GroupingSectionModel {
	availableGroupings: Loadable<readonly GroupingResponse[]>;
	activeGroupings: ReadonlyMap<string, ActiveGroupingState>;
	activateGrouping: (groupingId: string) => void;
	deactivateGrouping: (groupingId: string) => void;
	setGroupingValueSearchText: (groupingId: string, searchText: string) => void;
	setGroupingValueSelected: (groupingId: string, value: GroupData, selected: boolean) => void;
	loadPreviousGroupingValuesPage: (groupingId: string) => void;
	loadNextGroupingValuesPage: (groupingId: string) => void;
}

export interface QuerySectionModel {
	sortKeys: readonly SortKey[];
	queryStatus: QueryStatus;
	addSortKey: () => void;
	removeSortKey: (index: number) => void;
	setSortKeyField: (index: number, fieldName: string) => void;
	setSortKeyDirection: (index: number, direction: SortDirection) => void;
	applyFrame: () => void;
}

export interface InstanceResultsModel {
	results: Loadable<Page<InstanceQueryResult>>;
	refreshInstanceResults: () => void;
	loadPreviousInstancePage: () => void;
	loadNextInstancePage: () => void;
	openChapter?: (chapterId: string) => void;
}

export interface WorkflowDisplayPanelProps {
	workflowSelection: WorkflowSelectionModel;
	groupingSection: GroupingSectionModel;
	querySection: QuerySectionModel;
	instanceResults: InstanceResultsModel;
}
