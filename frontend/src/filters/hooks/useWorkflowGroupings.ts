import { readGroupingValuesFiltersGroupingsGroupingIdValuesGet } from "@/api/endpoints/filters/filters";
import type { GroupData, GroupingResponse, GroupValueCount } from "@/api/models";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Loadable, Page } from "../loadable";
import { errorMessage, requestError, WORKFLOW_VIEWER_PAGE_SIZE } from "./workflowViewerUtils";

export interface ActiveGroupingState {
	grouping: GroupingResponse;
	values: Loadable<Page<GroupValueCount>>;
	selectedValues: readonly GroupData[];
	search: string;
}

interface GroupingViewState extends ActiveGroupingState {
	offset: number;
}

export function useWorkflowGroupings(availableGroupings: Loadable<readonly GroupingResponse[]>) {
	const [activeGroupings, setActiveGroupings] = useState<ReadonlyMap<string, GroupingViewState>>(
		new Map(),
	);
	const groupingRequests = useRef(new Map<string, AbortController>());

	const resetGroupings = useCallback(() => {
		for (const controller of groupingRequests.current.values()) controller.abort();
		groupingRequests.current.clear();
		setActiveGroupings(new Map());
	}, []);

	useEffect(() => resetGroupings, [resetGroupings]);

	function updateGrouping(
		groupingId: string,
		update: (current: GroupingViewState) => GroupingViewState,
	) {
		setActiveGroupings((current) => {
			const state = current.get(groupingId);
			if (!state) return current;
			const next = new Map(current);
			next.set(groupingId, update(state));
			return next;
		});
	}

	function loadGroupingValues(grouping: GroupingResponse, searchText: string, offset: number) {
		groupingRequests.current.get(grouping.groupingId)?.abort();
		const controller = new AbortController();
		groupingRequests.current.set(grouping.groupingId, controller);
		void readGroupingValuesFiltersGroupingsGroupingIdValuesGet(
			grouping.groupingId,
			{
				search: searchText || undefined,
				limit: WORKFLOW_VIEWER_PAGE_SIZE,
				offset,
			},
			{ signal: controller.signal },
		)
			.then((response) => {
				if (controller.signal.aborted) return;
				if (response.status !== 200) {
					updateGrouping(grouping.groupingId, (current) => ({
						...current,
						values: {
							status: "error",
							message: requestError("Loading grouping values", response.status),
						},
					}));
					return;
				}
				updateGrouping(grouping.groupingId, (current) => ({
					...current,
					offset,
					values: {
						status: "ready",
						data: {
							items: response.data,
							start: response.data.length === 0 ? 0 : offset + 1,
							end: offset + response.data.length,
							hasPrevious: offset > 0,
							hasNext: response.data.length === WORKFLOW_VIEWER_PAGE_SIZE,
						},
					},
				}));
			})
			.catch((error: unknown) => {
				if (!controller.signal.aborted)
					updateGrouping(grouping.groupingId, (current) => ({
						...current,
						values: { status: "error", message: errorMessage(error) },
					}));
			});
	}

	function activateGrouping(groupingId: string) {
		if (availableGroupings.status !== "ready") return;
		const grouping = availableGroupings.data.find((item) => item.groupingId === groupingId);
		if (!grouping || activeGroupings.has(groupingId)) return;
		setActiveGroupings((current) => {
			const next = new Map(current);
			next.set(groupingId, {
				grouping,
				offset: 0,
				search: "",
				selectedValues: [],
				values: { status: "loading" },
			});
			return next;
		});
		loadGroupingValues(grouping, "", 0);
	}

	function deactivateGrouping(groupingId: string) {
		groupingRequests.current.get(groupingId)?.abort();
		groupingRequests.current.delete(groupingId);
		setActiveGroupings((current) => {
			const next = new Map(current);
			next.delete(groupingId);
			return next;
		});
	}

	function setGroupingValueSearchText(groupingId: string, searchText: string) {
		const state = activeGroupings.get(groupingId);
		if (!state) return;
		updateGrouping(groupingId, (current) => ({
			...current,
			offset: 0,
			search: searchText,
			values: { status: "loading" },
		}));
		loadGroupingValues(state.grouping, searchText, 0);
	}

	function setGroupingValueSelected(groupingId: string, value: GroupData, selected: boolean) {
		updateGrouping(groupingId, (current) => {
			const containsValue = current.selectedValues.some(
				(item) => item.type === value.type && item.value === value.value,
			);
			return {
				...current,
				selectedValues: selected
					? containsValue
						? current.selectedValues
						: [...current.selectedValues, value]
					: current.selectedValues.filter(
							(item) => item.type !== value.type || item.value !== value.value,
						),
			};
		});
	}

	function loadGroupingValuesPage(groupingId: string, direction: "previous" | "next") {
		const state = activeGroupings.get(groupingId);
		if (!state) return;
		const offset =
			direction === "previous"
				? Math.max(0, state.offset - WORKFLOW_VIEWER_PAGE_SIZE)
				: state.offset + WORKFLOW_VIEWER_PAGE_SIZE;
		loadGroupingValues(state.grouping, state.search, offset);
	}

	return {
		activeGroupings,
		activateGrouping,
		deactivateGrouping,
		setGroupingValueSearchText,
		setGroupingValueSelected,
		loadPreviousGroupingValuesPage: (groupingId: string) =>
			loadGroupingValuesPage(groupingId, "previous"),
		loadNextGroupingValuesPage: (groupingId: string) =>
			loadGroupingValuesPage(groupingId, "next"),
		resetGroupings,
	};
}
