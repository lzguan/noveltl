import type { LabelSourceRunnerFormModel } from "../../types";
import { LabelGroupSelector } from "./RunnerSelectors";
import { OutputWorkflowNameField } from "./OutputWorkflowNameField";
import { RunnerFormShell } from "./RunnerFormShell";

export function LabelSourceRunnerForm(props: LabelSourceRunnerFormModel) {
	const submitting = props.formStatus.status === "submitting";
	return (
		<RunnerFormShell
			title="Label source"
			description="Materialize the current labels in one label group as a new workflow."
			submitLabel="Create workflow"
			formStatus={props.formStatus}
			canSubmit={props.selectedLabelGroup !== null}
			submitRunnerOperation={props.submitLabelSourceRunner}
		>
			<LabelGroupSelector
				labelGroups={props.labelGroups}
				keyword={props.labelGroupKeyword}
				selectedLabelGroup={props.selectedLabelGroup}
				disabled={submitting}
				setLabelGroupSearchKeyword={props.setLabelGroupSearchKeyword}
				selectLabelGroup={props.selectLabelGroup}
			/>
			<OutputWorkflowNameField
				id="label-source-output-name"
				outputWorkflowName={props.outputWorkflowName}
				disabled={submitting}
				setOutputWorkflowName={props.setOutputWorkflowName}
			/>
		</RunnerFormShell>
	);
}
