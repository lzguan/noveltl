import type { MapRunnerFormModel } from "../../types";
import { useWorkflowFunctionRunnerForm } from "./useWorkflowFunctionRunnerForm";

export function useMapRunnerForm(novelId: string, enabled: boolean): MapRunnerFormModel {
	const draft = useWorkflowFunctionRunnerForm(novelId, enabled, "map");
	return {
		workflows: {
			keyword: draft.workflowSearch.keyword,
			results: draft.workflowSearch.results,
			setSearchKeyword: draft.workflowSearch.setSearchKeyword,
		},
		functions: {
			keyword: draft.functionSearch.keyword,
			results: draft.functionSearch.results,
			setSearchKeyword: draft.functionSearch.setSearchKeyword,
		},
		selectedWorkflow: draft.selectedWorkflow,
		selectedFunctionDefinition: draft.selectedFunctionDefinition,
		outputWorkflowName: draft.outputWorkflowName,
		formStatus: draft.formStatus,
		selectSourceWorkflow: draft.selectWorkflow,
		selectFunctionDefinition: draft.selectFunctionDefinition,
		setOutputWorkflowName: draft.setOutputWorkflowName,
		submitMapRunner: draft.submitRunnerOperation,
	};
}
