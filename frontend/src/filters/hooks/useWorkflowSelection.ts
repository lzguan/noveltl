import {
	readGroupingFiltersGroupingsGroupingIdGet,
	readWorkflowFiltersWorkflowsWorkflowIdGet,
	readWorkflowGroupingsFiltersWorkflowsWorkflowIdGroupingsGet,
	readWorkflowsFiltersWorkflowsGet,
} from "@/api/endpoints/filters/filters";
import type { GroupingResponse } from "@/api/models";
import { useCallback, useEffect, useState } from "react";
import type { Loadable, WorkflowSelectionModel } from "../types";
import { errorMessage, requestError } from "./workflowViewerUtils";

export interface WorkflowSelectionState extends WorkflowSelectionModel {
	availableGroupings: Loadable<readonly GroupingResponse[]>;
}

export function useWorkflowSelection(novelId: string): WorkflowSelectionState {
	const [workflows, setWorkflows] = useState<WorkflowSelectionModel["workflows"]>({
		status: "loading",
	});
	const [searchText, setSearchText] = useState("");
	const [activeWorkflowId, setActiveWorkflowId] = useState<string | null>(null);
	const [activeWorkflow, setActiveWorkflow] = useState<WorkflowSelectionModel["activeWorkflow"]>({
		status: "idle",
	});
	const [availableGroupings, setAvailableGroupings] = useState<
		Loadable<readonly GroupingResponse[]>
	>({ status: "idle" });

	useEffect(() => {
		const controller = new AbortController();
		setSearchText("");
		setActiveWorkflowId(null);
		setActiveWorkflow({ status: "idle" });
		setAvailableGroupings({ status: "idle" });
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
			});
		return () => controller.abort();
	}, [novelId]);

	useEffect(() => {
		if (!activeWorkflowId) return;
		const workflowId = activeWorkflowId;
		const controller = new AbortController();
		setActiveWorkflow({ status: "loading" });
		setAvailableGroupings({ status: "loading" });

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
	}, [activeWorkflowId]);

	const selectWorkflow = useCallback((workflowId: string) => {
		setActiveWorkflow({ status: "loading" });
		setAvailableGroupings({ status: "loading" });
		setActiveWorkflowId(workflowId);
	}, []);

	return {
		workflows,
		searchText,
		activeWorkflowId,
		activeWorkflow,
		availableGroupings,
		setWorkflowSearchText: setSearchText,
		selectWorkflow,
	};
}
