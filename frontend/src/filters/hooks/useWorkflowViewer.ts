import type { Frame, SortKey, WorkflowResponse } from "@/api/models";
import { useEffect } from "react";
import type { ActiveGroupingState, TextReference, WorkflowDisplayPanelProps } from "../types";
import { useFrameDraft } from "./useFrameDraft";
import { useInstanceResults } from "./useInstanceResults";
import { useWorkflowGroupings } from "./useWorkflowGroupings";
import { useWorkflowSelection } from "./useWorkflowSelection";

export function buildWorkflowFrame(
	workflow: WorkflowResponse | null,
	activeGroupings: ReadonlyMap<string, ActiveGroupingState>,
	sortKeys: readonly SortKey[],
): Frame | null {
	if (!workflow) return null;
	return {
		workflowId: workflow.workflowId,
		groupFilters: [...activeGroupings.values()].map((state) => ({
			groupingId: state.grouping.groupingId,
			values: [...state.selectedValues],
		})),
		sortKeys: [...sortKeys],
	};
}

export function useWorkflowViewer(
	novelId: string,
	openTextReference?: (reference: TextReference) => void,
): WorkflowDisplayPanelProps {
	const workflowSelection = useWorkflowSelection(novelId);
	const groupingState = useWorkflowGroupings(workflowSelection.availableGroupings);
	const activeWorkflow =
		workflowSelection.activeWorkflow.status === "ready"
			? workflowSelection.activeWorkflow.data
			: null;
	const frameDraft = useFrameDraft(activeWorkflow);
	const instanceResults = useInstanceResults();
	const { resetGroupings } = groupingState;
	const { resetFrameDraft } = frameDraft;
	const { resetInstanceResults } = instanceResults;

	useEffect(() => {
		resetGroupings();
		resetFrameDraft();
		resetInstanceResults();
	}, [novelId, resetGroupings, resetFrameDraft, resetInstanceResults]);

	function selectWorkflow(workflowId: string) {
		resetGroupings();
		resetFrameDraft();
		resetInstanceResults();
		workflowSelection.selectWorkflow(workflowId);
	}

	function applyFrame() {
		const frame = buildWorkflowFrame(
			activeWorkflow,
			groupingState.activeGroupings,
			frameDraft.sortKeys,
		);
		if (frame) instanceResults.applyFrame(frame);
	}

	return {
		workflowSelection: {
			workflows: workflowSelection.workflows,
			searchText: workflowSelection.searchText,
			activeWorkflowId: workflowSelection.activeWorkflowId,
			activeWorkflow: workflowSelection.activeWorkflow,
			setWorkflowSearchText: workflowSelection.setWorkflowSearchText,
			selectWorkflow,
			refreshWorkflowList: workflowSelection.refreshWorkflowList,
		},
		groupingSection: {
			availableGroupings: workflowSelection.availableGroupings,
			activeGroupings: groupingState.activeGroupings,
			activateGrouping: groupingState.activateGrouping,
			deactivateGrouping: groupingState.deactivateGrouping,
			setGroupingValueSearchText: groupingState.setGroupingValueSearchText,
			setGroupingValueSelected: groupingState.setGroupingValueSelected,
			loadPreviousGroupingValuesPage: groupingState.loadPreviousGroupingValuesPage,
			loadNextGroupingValuesPage: groupingState.loadNextGroupingValuesPage,
		},
		querySection: {
			sortKeys: frameDraft.sortKeys,
			queryStatus: instanceResults.queryStatus,
			addSortKey: frameDraft.addSortKey,
			removeSortKey: frameDraft.removeSortKey,
			setSortKeyField: frameDraft.setSortKeyField,
			setSortKeyDirection: frameDraft.setSortKeyDirection,
			applyFrame,
		},
		instanceResults: {
			results: instanceResults.results,
			commitInstanceField: instanceResults.commitInstanceField,
			refreshInstanceResults: instanceResults.refreshInstanceResults,
			loadPreviousInstancePage: instanceResults.loadPreviousInstancePage,
			loadNextInstancePage: instanceResults.loadNextInstancePage,
			openTextReference,
		},
	};
}
