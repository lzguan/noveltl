import type { GroupRunnerFormModel } from "../../types";
import { RunnerFormShell } from "./RunnerFormShell";
import { WorkflowFunctionFields } from "./WorkflowFunctionFields";

export function GroupRunnerForm(props: GroupRunnerFormModel) {
	const submitting = props.formStatus.status === "submitting";
	return (
		<RunnerFormShell
			title="Group workflow"
			description="Attach one immutable scalar grouping value to every workflow instance."
			submitLabel="Create grouping"
			formStatus={props.formStatus}
			canSubmit={props.selectedWorkflow !== null && props.selectedFunctionDefinition !== null}
			submitRunnerOperation={props.submitGroupRunner}
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
