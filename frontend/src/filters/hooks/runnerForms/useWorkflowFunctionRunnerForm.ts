import type { FunctionDefinitionMeta, WorkflowSummary } from "@/api/models";
import { useCallback, useState } from "react";
import { useAsyncSearch } from "../useAsyncSearch";
import { fetchCompletedWorkflowOptions, fetchFunctionDefinitionOptions } from "./useRunnerOptions";

export function useWorkflowFunctionRunnerForm(
	novelId: string,
	enabled: boolean,
	successTarget: "workflow" | "grouping",
) {
	const fetchWorkflows = useCallback(
		(keyword: string, signal: AbortSignal) =>
			fetchCompletedWorkflowOptions(novelId, keyword, signal),
		[novelId],
	);
	const workflows = useAsyncSearch(fetchWorkflows, enabled);
	const functions = useAsyncSearch(fetchFunctionDefinitionOptions, enabled);
	const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowSummary | null>(null);
	const [selectedFunctionDefinition, setSelectedFunctionDefinition] =
		useState<FunctionDefinitionMeta | null>(null);
	const [outputWorkflowName, setOutputWorkflowNameState] = useState("");
	const [formStatus, setFormStatus] = useState<
		| { status: "idle" }
		| { status: "submitting" }
		| { status: "succeeded"; target: "workflow" | "grouping" }
		| { status: "error"; message: string }
	>({ status: "idle" });

	function resetRequestStatus() {
		setFormStatus({ status: "idle" });
	}

	function selectWorkflow(workflow: WorkflowSummary | null) {
		setSelectedWorkflow(workflow);
		resetRequestStatus();
	}

	function selectFunctionDefinition(definition: FunctionDefinitionMeta | null) {
		setSelectedFunctionDefinition(definition);
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
		setFormStatus({ status: "succeeded", target: successTarget });
	}

	function resetForm() {
		setSelectedWorkflow(null);
		setSelectedFunctionDefinition(null);
		setOutputWorkflowNameState("");
		workflows.setSearchKeyword("");
		functions.setSearchKeyword("");
		setFormStatus({ status: "idle" });
	}

	return {
		workflows,
		functions,
		selectedWorkflow,
		selectedFunctionDefinition,
		outputWorkflowName,
		formStatus,
		selectWorkflow,
		selectFunctionDefinition,
		setOutputWorkflowName,
		preSend,
		onSendError,
		onSendSuccess,
		resetForm,
	};
}
