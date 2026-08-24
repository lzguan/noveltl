import { runPythonLabelSource } from "@/api/endpoints/filters/filters";
import { apiErrorMessage, requestErrorMessage } from "../../apiErrors";
import { useLabelSourceRunnerForm } from "../../hooks/runnerForms/useLabelSourceRunnerForm";
import { LabelGroupSelector } from "./RunnerSelectors";
import { OutputWorkflowNameField } from "./OutputWorkflowNameField";
import { RunnerFormShell } from "./RunnerFormShell";

export function LabelSourceRunnerForm({ novelId, enabled }: { novelId: string; enabled: boolean }) {
	const props = useLabelSourceRunnerForm(novelId, enabled);
	const submitting = props.formStatus.status === "submitting";

	async function submitLabelSourceRunner() {
		if (!props.selectedLabelGroup) return;
		props.preSend();
		const trimmedName = props.outputWorkflowName.trim();
		try {
			const response = await runPythonLabelSource({
				labelGroupId: props.selectedLabelGroup.labelGroupId,
				...(trimmedName ? { outputName: trimmedName } : {}),
			});
			if (response.status === 202) {
				props.onSendSuccess();
			} else {
				props.onSendError(
					apiErrorMessage(response.data, "Could not create the label-source workflow."),
				);
			}
		} catch (error) {
			props.onSendError(requestErrorMessage(error));
		}
	}

	return (
		<RunnerFormShell
			title="Label source"
			description="Materialize the current labels in one label group as a new workflow."
			submitLabel="Create workflow"
			formStatus={props.formStatus}
			canSubmit={props.selectedLabelGroup !== null}
			submitRunnerOperation={submitLabelSourceRunner}
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
