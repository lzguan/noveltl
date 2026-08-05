import type { GroupRunnerFormModel } from "../../types";
import { useWorkflowFunctionRunnerForm } from "./useWorkflowFunctionRunnerForm";

export function useGroupRunnerForm(novelId: string, enabled: boolean): GroupRunnerFormModel {
	const draft = useWorkflowFunctionRunnerForm(novelId, enabled, "group");
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
		formStatus: draft.formStatus,
		selectWorkflow: draft.selectWorkflow,
		selectFunctionDefinition: draft.selectFunctionDefinition,
		submitGroupRunner: draft.submitRunnerOperation,
	};
}
