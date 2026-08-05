import type { FunctionDefinitionMeta, LabelGroup, WorkflowSummary } from "@/api/models";
import type { Loadable, SearchOptionsModel } from "../../types";
import { workflowLabel } from "../panelUi";
import { SearchSelector } from "../SearchSelector";

function functionLabel(definition: FunctionDefinitionMeta) {
	return `${definition.namespace}.${definition.functionName}`;
}

export function LabelGroupSelector({
	labelGroups,
	keyword,
	selectedLabelGroup,
	disabled,
	setLabelGroupSearchKeyword,
	selectLabelGroup,
}: {
	labelGroups: Loadable<readonly LabelGroup[]>;
	keyword: string;
	selectedLabelGroup: LabelGroup | null;
	disabled: boolean;
	setLabelGroupSearchKeyword: (keyword: string) => void;
	selectLabelGroup: (labelGroup: LabelGroup | null) => void;
}) {
	return (
		<SearchSelector
			id="runner-label-group"
			label="Label group"
			keyword={keyword}
			results={labelGroups}
			selectedResult={selectedLabelGroup}
			placeholder="Search label groups"
			emptyMessage="No label groups found."
			disabled={disabled}
			getResultKey={(labelGroup) => labelGroup.labelGroupId}
			getResultLabel={(labelGroup) => labelGroup.labelGroupName}
			setSearchKeyword={setLabelGroupSearchKeyword}
			selectSearchResult={selectLabelGroup}
		/>
	);
}

export function WorkflowSearchSelector({
	id,
	label,
	search,
	selectedWorkflow,
	disabled,
	selectWorkflow,
}: {
	id: string;
	label: string;
	search: SearchOptionsModel<WorkflowSummary>;
	selectedWorkflow: WorkflowSummary | null;
	disabled: boolean;
	selectWorkflow: (workflow: WorkflowSummary | null) => void;
}) {
	return (
		<SearchSelector
			id={id}
			label={label}
			keyword={search.keyword}
			results={search.results}
			selectedResult={selectedWorkflow}
			placeholder="Search completed workflows"
			emptyMessage="No completed workflows found. Refine your search if necessary."
			disabled={disabled}
			getResultKey={(workflow) => workflow.workflowId}
			getResultLabel={workflowLabel}
			setSearchKeyword={search.setSearchKeyword}
			selectSearchResult={selectWorkflow}
		/>
	);
}

export function FunctionSearchSelector({
	id,
	search,
	selectedFunctionDefinition,
	disabled,
	selectFunctionDefinition,
}: {
	id: string;
	search: SearchOptionsModel<FunctionDefinitionMeta>;
	selectedFunctionDefinition: FunctionDefinitionMeta | null;
	disabled: boolean;
	selectFunctionDefinition: (definition: FunctionDefinitionMeta | null) => void;
}) {
	return (
		<SearchSelector
			id={id}
			label="Function"
			keyword={search.keyword}
			results={search.results}
			selectedResult={selectedFunctionDefinition}
			placeholder="Search saved functions"
			emptyMessage="No functions found. Refine your search if necessary."
			disabled={disabled}
			getResultKey={(definition) => definition.functionDefinitionId}
			getResultLabel={functionLabel}
			setSearchKeyword={search.setSearchKeyword}
			selectSearchResult={selectFunctionDefinition}
		/>
	);
}
