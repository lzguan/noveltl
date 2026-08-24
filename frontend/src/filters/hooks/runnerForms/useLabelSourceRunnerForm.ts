import type { LabelGroup } from "@/api/models";
import { useState } from "react";
import { useLabelGroupOptions } from "./useRunnerOptions";

export function useLabelSourceRunnerForm(novelId: string, enabled: boolean) {
	const labelGroups = useLabelGroupOptions(novelId, enabled);
	const [labelGroupKeyword, setLabelGroupKeyword] = useState("");
	const [selectedLabelGroup, setSelectedLabelGroup] = useState<LabelGroup | null>(null);
	const [outputWorkflowName, setOutputWorkflowNameState] = useState("");
	const [formStatus, setFormStatus] = useState<
		| { status: "idle" }
		| { status: "submitting" }
		| { status: "succeeded"; target: "workflow" }
		| { status: "error"; message: string }
	>({ status: "idle" });

	function resetRequestStatus() {
		setFormStatus({ status: "idle" });
	}

	function setLabelGroupSearchKeyword(keyword: string) {
		setLabelGroupKeyword(keyword);
	}

	function selectLabelGroup(labelGroup: LabelGroup | null) {
		setSelectedLabelGroup(labelGroup);
		resetRequestStatus();
	}

	function setOutputWorkflowName(name: string) {
		setOutputWorkflowNameState(name);
		resetRequestStatus();
	}

	function preSend() {
		setFormStatus({ status: "submitting" });
	}

	function onSendError(message: string) {
		setFormStatus({ status: "error", message });
	}

	function onSendSuccess() {
		setFormStatus({ status: "succeeded", target: "workflow" });
	}

	function resetForm() {
		setLabelGroupKeyword("");
		setSelectedLabelGroup(null);
		setOutputWorkflowNameState("");
		setFormStatus({ status: "idle" });
	}

	return {
		labelGroups,
		labelGroupKeyword,
		selectedLabelGroup,
		outputWorkflowName,
		formStatus,
		setLabelGroupSearchKeyword,
		selectLabelGroup,
		setOutputWorkflowName,
		preSend,
		onSendError,
		onSendSuccess,
		resetForm,
	};
}
