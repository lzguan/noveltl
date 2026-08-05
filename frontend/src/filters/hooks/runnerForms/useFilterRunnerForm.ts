import type { FilterRunnerFormModel } from "../../types";
import { useWorkflowFunctionRunnerForm } from "./useWorkflowFunctionRunnerForm";

export function useFilterRunnerForm(novelId: string, enabled: boolean): FilterRunnerFormModel {
	const draft = useWorkflowFunctionRunnerForm(novelId, enabled, "filter");
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
		submitFilterRunner: draft.submitRunnerOperation,
	};
}
