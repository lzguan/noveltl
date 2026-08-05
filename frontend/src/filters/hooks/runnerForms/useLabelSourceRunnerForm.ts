import { runPythonLabelSource } from "@/api/endpoints/filters/filters";
import type { LabelGroup } from "@/api/models";
import { useCallback, useEffect, useRef, useState } from "react";
import { apiErrorMessage, requestErrorMessage } from "../../apiErrors";
import type { LabelSourceRunnerFormModel, RunnerFormStatus } from "../../types";
import { useLabelGroupOptions } from "./useRunnerOptions";

export function useLabelSourceRunnerForm(
	novelId: string,
	enabled: boolean,
): LabelSourceRunnerFormModel {
	const labelGroups = useLabelGroupOptions(novelId, enabled);
	const [labelGroupKeyword, setLabelGroupKeyword] = useState("");
	const [selectedLabelGroup, setSelectedLabelGroup] = useState<LabelGroup | null>(null);
	const [outputWorkflowName, setOutputWorkflowNameState] = useState("");
	const [formStatus, setFormStatus] = useState<RunnerFormStatus>({ status: "idle" });
	const activeRequest = useRef<AbortController | null>(null);

	const cancelActiveRequest = useCallback(() => {
		activeRequest.current?.abort();
		activeRequest.current = null;
	}, []);

	useEffect(() => cancelActiveRequest, [cancelActiveRequest]);

	useEffect(() => {
		cancelActiveRequest();
		setLabelGroupKeyword("");
		setSelectedLabelGroup(null);
		setOutputWorkflowNameState("");
		setFormStatus({ status: "idle" });
	}, [cancelActiveRequest, novelId]);

	useEffect(() => {
		if (!enabled) {
			cancelActiveRequest();
			setFormStatus({ status: "idle" });
		}
	}, [cancelActiveRequest, enabled]);

	function resetRequestStatus() {
		cancelActiveRequest();
		setFormStatus({ status: "idle" });
	}

	function selectLabelGroup(labelGroup: LabelGroup | null) {
		setSelectedLabelGroup(labelGroup);
		resetRequestStatus();
	}

	function setOutputWorkflowName(name: string) {
		setOutputWorkflowNameState(name);
		resetRequestStatus();
	}

	async function submitLabelSourceRunner() {
		if (!selectedLabelGroup) return;
		cancelActiveRequest();
		const controller = new AbortController();
		activeRequest.current = controller;
		setFormStatus({ status: "submitting" });
		const trimmedName = outputWorkflowName.trim();
		try {
			const response = await runPythonLabelSource(
				{
					labelGroupId: selectedLabelGroup.labelGroupId,
					...(trimmedName ? { outputName: trimmedName } : {}),
				},
				{ signal: controller.signal },
			);
			if (controller.signal.aborted) return;
			if (response.status === 202) {
				setFormStatus({ status: "succeeded", target: "workflow" });
			} else {
				setFormStatus({
					status: "error",
					message: apiErrorMessage(
						response.data,
						"Could not create the label-source workflow.",
					),
				});
			}
		} catch (error) {
			if (!controller.signal.aborted)
				setFormStatus({ status: "error", message: requestErrorMessage(error) });
		} finally {
			if (activeRequest.current === controller) activeRequest.current = null;
		}
	}

	return {
		labelGroups,
		labelGroupKeyword,
		selectedLabelGroup,
		outputWorkflowName,
		formStatus,
		setLabelGroupSearchKeyword: setLabelGroupKeyword,
		selectLabelGroup,
		setOutputWorkflowName,
		submitLabelSourceRunner,
	};
}
