import type { FilterRunnerFormModel } from "../../types";
import { OutputWorkflowNameField } from "./OutputWorkflowNameField";
import { RunnerFormShell } from "./RunnerFormShell";
import { WorkflowFunctionFields } from "./WorkflowFunctionFields";

export function FilterRunnerForm(props: FilterRunnerFormModel) {
	const submitting = props.formStatus.status === "submitting";
	return (
		<RunnerFormShell
			title="Filter workflow"
			description="Keep source instances for which an object-to-boolean function returns true."
			submitLabel="Create workflow"
			formStatus={props.formStatus}
			canSubmit={props.selectedWorkflow !== null && props.selectedFunctionDefinition !== null}
			submitRunnerOperation={props.submitFilterRunner}
		>
			<WorkflowFunctionFields
				idPrefix="filter-runner"
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
				id="filter-runner-output-name"
				outputWorkflowName={props.outputWorkflowName}
				disabled={submitting}
				setOutputWorkflowName={props.setOutputWorkflowName}
			/>
		</RunnerFormShell>
	);
}
