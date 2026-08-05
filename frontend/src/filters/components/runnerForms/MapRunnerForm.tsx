import type { MapRunnerFormModel } from "../../types";
import { OutputWorkflowNameField } from "./OutputWorkflowNameField";
import { RunnerFormShell } from "./RunnerFormShell";
import { WorkflowFunctionFields } from "./WorkflowFunctionFields";

export function MapRunnerForm(props: MapRunnerFormModel) {
	const submitting = props.formStatus.status === "submitting";
	return (
		<RunnerFormShell
			title="Map workflow"
			description="Apply an object-to-object function to every source instance."
			submitLabel="Create workflow"
			formStatus={props.formStatus}
			canSubmit={props.selectedWorkflow !== null && props.selectedFunctionDefinition !== null}
			submitRunnerOperation={props.submitMapRunner}
		>
			<WorkflowFunctionFields
				idPrefix="map-runner"
				workflowLabel="Source workflow"
				workflows={props.workflows}
				functions={props.functions}
				selectedWorkflow={props.selectedWorkflow}
				selectedFunctionDefinition={props.selectedFunctionDefinition}
				disabled={submitting}
				selectWorkflow={props.selectSourceWorkflow}
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
