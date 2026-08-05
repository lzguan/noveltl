import type {
	GroupData,
	FunctionDefinitionResponse,
	FunctionDefinitionMeta,
	GroupingResponse,
	GroupValueCount,
	InstanceQueryResult,
	LabelRef,
	LabelGroup,
	Signature,
	SortKey,
	SortDirection,
	TextSpan,
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

export type TextReference =
	| { type: "labelRef"; value: LabelRef }
	| { type: "textSpan"; value: TextSpan };

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
	refreshWorkflowList: () => void;
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
	openTextReference?: (reference: TextReference) => void;
}

export interface WorkflowDisplayPanelProps {
	workflowSelection: WorkflowSelectionModel;
	groupingSection: GroupingSectionModel;
	querySection: QuerySectionModel;
	instanceResults: InstanceResultsModel;
}

export type FunctionDefinitionFormStatus =
	| { status: "idle" }
	| { status: "validating" }
	| { status: "validated"; signature: Signature }
	| { status: "uploading" }
	| { status: "uploaded"; functionDefinition: FunctionDefinitionResponse }
	| { status: "error"; action: "validate" | "upload"; message: string };

export interface FunctionDefinitionFormModel {
	functionNamespace: string;
	functionName: string;
	functionDefinitionText: string;
	functionDefinitionError: string | null;
	formStatus: FunctionDefinitionFormStatus;
	setFunctionNamespace: (namespace: string) => void;
	setFunctionName: (name: string) => void;
	setFunctionDefinitionText: (definitionText: string) => void;
	validateFunctionDefinition: () => Promise<void>;
	uploadFunctionDefinition: () => Promise<void>;
}

export type RunnerOperation = "labelSource" | "map" | "filter" | "group";

export type RunnerFormStatus =
	| { status: "idle" }
	| { status: "submitting" }
	| { status: "succeeded"; target: "workflow" | "grouping" }
	| { status: "error"; message: string };

export interface SearchOptionsModel<T> {
	keyword: string;
	results: Loadable<readonly T[]>;
	setSearchKeyword: (keyword: string) => void;
}

export interface LabelSourceRunnerFormModel {
	labelGroups: Loadable<readonly LabelGroup[]>;
	labelGroupKeyword: string;
	selectedLabelGroup: LabelGroup | null;
	outputWorkflowName: string;
	formStatus: RunnerFormStatus;
	setLabelGroupSearchKeyword: (keyword: string) => void;
	selectLabelGroup: (labelGroup: LabelGroup | null) => void;
	setOutputWorkflowName: (name: string) => void;
	submitLabelSourceRunner: () => Promise<void>;
}

export interface WorkflowFunctionRunnerOptionsModel {
	workflows: SearchOptionsModel<WorkflowSummary>;
	functions: SearchOptionsModel<FunctionDefinitionMeta>;
	selectedWorkflow: WorkflowSummary | null;
	selectedFunctionDefinition: FunctionDefinitionMeta | null;
}

export interface MapRunnerFormModel extends WorkflowFunctionRunnerOptionsModel {
	outputWorkflowName: string;
	formStatus: RunnerFormStatus;
	selectSourceWorkflow: (workflow: WorkflowSummary | null) => void;
	selectFunctionDefinition: (definition: FunctionDefinitionMeta | null) => void;
	setOutputWorkflowName: (name: string) => void;
	submitMapRunner: () => Promise<void>;
}

export interface FilterRunnerFormModel extends WorkflowFunctionRunnerOptionsModel {
	outputWorkflowName: string;
	formStatus: RunnerFormStatus;
	selectSourceWorkflow: (workflow: WorkflowSummary | null) => void;
	selectFunctionDefinition: (definition: FunctionDefinitionMeta | null) => void;
	setOutputWorkflowName: (name: string) => void;
	submitFilterRunner: () => Promise<void>;
}

export interface GroupRunnerFormModel extends WorkflowFunctionRunnerOptionsModel {
	formStatus: RunnerFormStatus;
	selectWorkflow: (workflow: WorkflowSummary | null) => void;
	selectFunctionDefinition: (definition: FunctionDefinitionMeta | null) => void;
	submitGroupRunner: () => Promise<void>;
}

export interface RunnerPanelModel {
	activeRunnerOperation: RunnerOperation;
	labelSourceForm: LabelSourceRunnerFormModel;
	mapForm: MapRunnerFormModel;
	filterForm: FilterRunnerFormModel;
	groupForm: GroupRunnerFormModel;
	selectRunnerOperation: (operation: RunnerOperation) => void;
}
