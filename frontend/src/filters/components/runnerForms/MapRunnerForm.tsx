import { runPythonMap } from "@/api/endpoints/filters/filters";
import { apiErrorMessage, requestErrorMessage } from "../../apiErrors";
import { useWorkflowFunctionRunnerForm } from "../../hooks/runnerForms/useWorkflowFunctionRunnerForm";
import { OutputWorkflowNameField } from "./OutputWorkflowNameField";
import { RunnerFormShell } from "./RunnerFormShell";
import { WorkflowFunctionFields } from "./WorkflowFunctionFields";

export function MapRunnerForm({ novelId, enabled }: { novelId: string; enabled: boolean }) {
	const props = useWorkflowFunctionRunnerForm(novelId, enabled, "workflow");
	const submitting = props.formStatus.status === "submitting";

	async function submitMapRunner() {
		if (!props.selectedWorkflow || !props.selectedFunctionDefinition) return;
		props.preSend();
		const trimmedName = props.outputWorkflowName.trim();
		try {
			const response = await runPythonMap({
				sourceWorkflowId: props.selectedWorkflow.workflowId,
				functionDefinitionId: props.selectedFunctionDefinition.functionDefinitionId,
				...(trimmedName ? { outputName: trimmedName } : {}),
			});
			if (response.status === 202) {
				props.onSendSuccess();
			} else {
				props.onSendError(
					apiErrorMessage(response.data, "Could not run the map operation."),
				);
			}
		} catch (error) {
			props.onSendError(requestErrorMessage(error));
		}
	}

	return (
		<RunnerFormShell
			title="Map workflow"
			description="Apply an object-to-object function to every source instance."
			submitLabel="Create workflow"
			formStatus={props.formStatus}
			canSubmit={props.selectedWorkflow !== null && props.selectedFunctionDefinition !== null}
			submitRunnerOperation={submitMapRunner}
		>
			<WorkflowFunctionFields
				idPrefix="map-runner"
				workflowLabel="Source workflow"
				workflows={props.workflows}
				functions={props.functions}
				selectedWorkflow={props.selectedWorkflow}
				selectedFunctionDefinition={props.selectedFunctionDefinition}
				disabled={submitting}
				selectWorkflow={props.selectWorkflow}
				selectFunctionDefinition={props.selectFunctionDefinition}
			/>
			<OutputWorkflowNameField
				id="map-runner-output-name"
				outputWorkflowName={props.outputWorkflowName}
				disabled={submitting}
				setOutputWorkflowName={props.setOutputWorkflowName}
			/>
		</RunnerFormShell>
	);
}
