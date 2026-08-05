import type { FunctionDefinitionMeta, WorkflowSummary } from "@/api/models";
import type { SearchOptionsModel } from "../../types";
import { FunctionSearchSelector, WorkflowSearchSelector } from "./RunnerSelectors";

export function WorkflowFunctionFields({
	idPrefix,
	workflowLabel,
	workflows,
	functions,
	selectedWorkflow,
	selectedFunctionDefinition,
	disabled,
	selectWorkflow,
	selectFunctionDefinition,
}: {
	idPrefix: string;
	workflowLabel: string;
	workflows: SearchOptionsModel<WorkflowSummary>;
	functions: SearchOptionsModel<FunctionDefinitionMeta>;
	selectedWorkflow: WorkflowSummary | null;
	selectedFunctionDefinition: FunctionDefinitionMeta | null;
	disabled: boolean;
	selectWorkflow: (workflow: WorkflowSummary | null) => void;
	selectFunctionDefinition: (definition: FunctionDefinitionMeta | null) => void;
}) {
	return (
		<>
			<WorkflowSearchSelector
				id={`${idPrefix}-workflow`}
				label={workflowLabel}
				search={workflows}
				selectedWorkflow={selectedWorkflow}
				disabled={disabled}
				selectWorkflow={selectWorkflow}
			/>
			<FunctionSearchSelector
				id={`${idPrefix}-function`}
				search={functions}
				selectedFunctionDefinition={selectedFunctionDefinition}
				disabled={disabled}
				selectFunctionDefinition={selectFunctionDefinition}
			/>
		</>
	);
}
