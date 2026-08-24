import { runPythonGroup } from "@/api/endpoints/filters/filters";
import { apiErrorMessage, requestErrorMessage } from "../../apiErrors";
import { useWorkflowFunctionRunnerForm } from "../../hooks/runnerForms/useWorkflowFunctionRunnerForm";
import { RunnerFormShell } from "./RunnerFormShell";
import { WorkflowFunctionFields } from "./WorkflowFunctionFields";

export function GroupRunnerForm({ novelId, enabled }: { novelId: string; enabled: boolean }) {
	const props = useWorkflowFunctionRunnerForm(novelId, enabled, "grouping");
	const submitting = props.formStatus.status === "submitting";

	async function submitGroupRunner() {
		if (!props.selectedWorkflow || !props.selectedFunctionDefinition) return;
		props.preSend();
		try {
			const response = await runPythonGroup({
				workflowId: props.selectedWorkflow.workflowId,
				functionDefinitionId: props.selectedFunctionDefinition.functionDefinitionId,
			});
			if (response.status === 202) {
				props.onSendSuccess();
			} else {
				props.onSendError(
					apiErrorMessage(response.data, "Could not run the group operation."),
				);
			}
		} catch (error) {
			props.onSendError(requestErrorMessage(error));
		}
	}

	return (
		<RunnerFormShell
			title="Group workflow"
			description="Attach one immutable scalar grouping value to every workflow instance."
			submitLabel="Create grouping"
			formStatus={props.formStatus}
			canSubmit={props.selectedWorkflow !== null && props.selectedFunctionDefinition !== null}
			submitRunnerOperation={submitGroupRunner}
		>
			<WorkflowFunctionFields
				idPrefix="group-runner"
				workflowLabel="Workflow"
				workflows={props.workflows}
				functions={props.functions}
				selectedWorkflow={props.selectedWorkflow}
				selectedFunctionDefinition={props.selectedFunctionDefinition}
				disabled={submitting}
				selectWorkflow={props.selectWorkflow}
				selectFunctionDefinition={props.selectFunctionDefinition}
			/>
		</RunnerFormShell>
	);
}
