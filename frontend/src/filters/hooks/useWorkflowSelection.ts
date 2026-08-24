import {
	readGroupingFiltersGroupingsGroupingIdGet,
	readWorkflowFiltersWorkflowsWorkflowIdGet,
	readWorkflowGroupingsFiltersWorkflowsWorkflowIdGroupingsGet,
	readWorkflowsFiltersWorkflowsGet,
} from "@/api/endpoints/filters/filters";
import type { GroupingResponse, WorkflowResponse, WorkflowSummary } from "@/api/models";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Loadable } from "../loadable";
import { errorMessage, requestError } from "./workflowViewerUtils";

export interface WorkflowSelectionState {
	workflows: Loadable<readonly WorkflowSummary[]>;
	searchText: string;
	activeWorkflowId: string | null;
	activeWorkflow: Loadable<WorkflowResponse>;
	availableGroupings: Loadable<readonly GroupingResponse[]>;
	setWorkflowSearchText: (searchText: string) => void;
	selectWorkflow: (workflowId: string) => void;
	refreshWorkflowList: () => void;
}

export function useWorkflowSelection(novelId: string): WorkflowSelectionState {
	const [workflows, setWorkflows] = useState<Loadable<readonly WorkflowSummary[]>>({
		status: "loading",
	});
	const [searchText, setSearchText] = useState("");
	const [activeWorkflowId, setActiveWorkflowId] = useState<string | null>(null);
	const [activeWorkflowLoadRevision, setActiveWorkflowLoadRevision] = useState(0);
	const [activeWorkflow, setActiveWorkflow] = useState<Loadable<WorkflowResponse>>({
		status: "idle",
	});
	const [availableGroupings, setAvailableGroupings] = useState<
		Loadable<readonly GroupingResponse[]>
	>({ status: "idle" });
	const workflowListRequest = useRef<AbortController | null>(null);

	const refreshWorkflowList = useCallback(() => {
		workflowListRequest.current?.abort();
		const controller = new AbortController();
		workflowListRequest.current = controller;
		setWorkflows({ status: "loading" });
		void readWorkflowsFiltersWorkflowsGet(
			{ novelId, limit: 100 },
			{ signal: controller.signal },
		)
			.then((response) => {
				if (controller.signal.aborted) return;
				if (response.status === 200) {
					setWorkflows({ status: "ready", data: response.data });
				} else {
					setWorkflows({
						status: "error",
						message: requestError("Loading workflows", response.status),
					});
				}
			})
			.catch((error: unknown) => {
				if (!controller.signal.aborted)
					setWorkflows({ status: "error", message: errorMessage(error) });
			})
			.finally(() => {
				if (workflowListRequest.current === controller) workflowListRequest.current = null;
			});
	}, [novelId]);

	useEffect(() => {
		// This starts the initial request, including its loading-state transition.
		// eslint-disable-next-line react-hooks/set-state-in-effect
		refreshWorkflowList();
		return () => workflowListRequest.current?.abort();
	}, [refreshWorkflowList]);

	useEffect(() => {
		if (!activeWorkflowId) return;
		const workflowId = activeWorkflowId;
		const controller = new AbortController();

		async function loadWorkflow() {
			const workflowResponse = await readWorkflowFiltersWorkflowsWorkflowIdGet(workflowId, {
				signal: controller.signal,
			});
			if (workflowResponse.status !== 200)
				throw new Error(requestError("Loading workflow", workflowResponse.status));
			if (!controller.signal.aborted)
				setActiveWorkflow({ status: "ready", data: workflowResponse.data });

			const groupingList = await readWorkflowGroupingsFiltersWorkflowsWorkflowIdGroupingsGet(
				workflowId,
				{ limit: 100 },
				{ signal: controller.signal },
			);
			if (groupingList.status !== 200)
				throw new Error(requestError("Loading groupings", groupingList.status));
			const groupingResponses = await Promise.all(
				groupingList.data.map((grouping) =>
					readGroupingFiltersGroupingsGroupingIdGet(grouping.groupingId, {
						signal: controller.signal,
					}),
				),
			);
			const groupings: GroupingResponse[] = [];
			for (const response of groupingResponses) {
				if (response.status !== 200)
					throw new Error(requestError("Loading a grouping", response.status));
				groupings.push(response.data);
			}
			if (!controller.signal.aborted)
				setAvailableGroupings({ status: "ready", data: groupings });
		}

		void loadWorkflow().catch((error: unknown) => {
			if (controller.signal.aborted) return;
			const message = errorMessage(error);
			setActiveWorkflow((current) =>
				current.status === "loading" ? { status: "error", message } : current,
			);
			setAvailableGroupings({ status: "error", message });
		});
		return () => controller.abort();
	}, [activeWorkflowId, activeWorkflowLoadRevision]);

	const selectWorkflow = useCallback((workflowId: string) => {
		setActiveWorkflow({ status: "loading" });
		setAvailableGroupings({ status: "loading" });
		setActiveWorkflowId(workflowId);
		setActiveWorkflowLoadRevision((revision) => revision + 1);
	}, []);

	return {
		workflows,
		searchText,
		activeWorkflowId,
		activeWorkflow,
		availableGroupings,
		setWorkflowSearchText: setSearchText,
		selectWorkflow,
		refreshWorkflowList,
	};
}
