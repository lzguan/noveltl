import { runPythonFilter, runPythonGroup, runPythonMap } from "@/api/endpoints/filters/filters";
import type { FunctionDefinitionMeta, WorkflowSummary } from "@/api/models";
import { useCallback, useEffect, useRef, useState } from "react";
import { apiErrorMessage, requestErrorMessage } from "../../apiErrors";
import type { RunnerFormStatus } from "../../types";
import { useAsyncSearch } from "../useAsyncSearch";
import { fetchCompletedWorkflowOptions, fetchFunctionDefinitionOptions } from "./useRunnerOptions";

type WorkflowFunctionRunnerOperation = "map" | "filter" | "group";

interface WorkflowFunctionRunnerDraft {
	workflowSearch: ReturnType<typeof useAsyncSearch<WorkflowSummary>>;
	functionSearch: ReturnType<typeof useAsyncSearch<FunctionDefinitionMeta>>;
	selectedWorkflow: WorkflowSummary | null;
	selectedFunctionDefinition: FunctionDefinitionMeta | null;
	outputWorkflowName: string;
	formStatus: RunnerFormStatus;
	selectWorkflow: (workflow: WorkflowSummary | null) => void;
	selectFunctionDefinition: (definition: FunctionDefinitionMeta | null) => void;
	setOutputWorkflowName: (name: string) => void;
	submitRunnerOperation: () => Promise<void>;
}

export function useWorkflowFunctionRunnerForm(
	novelId: string,
	enabled: boolean,
	operation: WorkflowFunctionRunnerOperation,
): WorkflowFunctionRunnerDraft {
	const fetchWorkflows = useCallback(
		(keyword: string, signal: AbortSignal) =>
			fetchCompletedWorkflowOptions(novelId, keyword, signal),
		[novelId],
	);
	const workflowSearch = useAsyncSearch(fetchWorkflows, enabled);
	const functionSearch = useAsyncSearch(fetchFunctionDefinitionOptions, enabled);
	const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowSummary | null>(null);
	const [selectedFunctionDefinition, setSelectedFunctionDefinition] =
		useState<FunctionDefinitionMeta | null>(null);
	const [outputWorkflowName, setOutputWorkflowNameState] = useState("");
	const [formStatus, setFormStatus] = useState<RunnerFormStatus>({ status: "idle" });
	const activeRequest = useRef<AbortController | null>(null);
	const setWorkflowSearchKeyword = workflowSearch.setSearchKeyword;
	const setFunctionSearchKeyword = functionSearch.setSearchKeyword;

	const cancelActiveRequest = useCallback(() => {
		activeRequest.current?.abort();
		activeRequest.current = null;
	}, []);

	useEffect(() => cancelActiveRequest, [cancelActiveRequest]);

	useEffect(() => {
		cancelActiveRequest();
		setSelectedWorkflow(null);
		setSelectedFunctionDefinition(null);
		setOutputWorkflowNameState("");
		setWorkflowSearchKeyword("");
		setFunctionSearchKeyword("");
		setFormStatus({ status: "idle" });
	}, [cancelActiveRequest, novelId, setFunctionSearchKeyword, setWorkflowSearchKeyword]);

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

	async function submitRunnerOperation() {
		if (!selectedWorkflow || !selectedFunctionDefinition) return;
		cancelActiveRequest();
		const controller = new AbortController();
		activeRequest.current = controller;
		setFormStatus({ status: "submitting" });
		const trimmedName = outputWorkflowName.trim();

		try {
			let accepted = false;
			let responseError: unknown = null;
			if (operation === "map") {
				const response = await runPythonMap(
					{
						sourceWorkflowId: selectedWorkflow.workflowId,
						functionDefinitionId: selectedFunctionDefinition.functionDefinitionId,
						...(trimmedName ? { outputName: trimmedName } : {}),
					},
					{ signal: controller.signal },
				);
				accepted = response.status === 202;
				if (!accepted) responseError = response.data;
			} else if (operation === "filter") {
				const response = await runPythonFilter(
					{
						sourceWorkflowId: selectedWorkflow.workflowId,
						functionDefinitionId: selectedFunctionDefinition.functionDefinitionId,
						...(trimmedName ? { outputName: trimmedName } : {}),
					},
					{ signal: controller.signal },
				);
				accepted = response.status === 202;
				if (!accepted) responseError = response.data;
			} else {
				const response = await runPythonGroup(
					{
						workflowId: selectedWorkflow.workflowId,
						functionDefinitionId: selectedFunctionDefinition.functionDefinitionId,
					},
					{ signal: controller.signal },
				);
				accepted = response.status === 202;
				if (!accepted) responseError = response.data;
			}

			if (controller.signal.aborted) return;
			if (accepted) {
				setFormStatus({
					status: "succeeded",
					target: operation === "group" ? "grouping" : "workflow",
				});
			} else {
				setFormStatus({
					status: "error",
					message: apiErrorMessage(
						responseError,
						`Could not run the ${operation} operation.`,
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
		workflowSearch,
		functionSearch,
		selectedWorkflow,
		selectedFunctionDefinition,
		outputWorkflowName,
		formStatus,
		selectWorkflow,
		selectFunctionDefinition,
		setOutputWorkflowName,
		submitRunnerOperation,
	};
}
