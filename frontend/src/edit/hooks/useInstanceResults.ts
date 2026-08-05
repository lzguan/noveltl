import { readInstancesAdvancedFiltersInstancesQueryPost } from "@/api/endpoints/filters/filters";
import type { Frame } from "@/api/models";
import { useCallback, useEffect, useRef, useState } from "react";
import type { InstanceResultsModel, QueryStatus } from "../panels/filters/types";
import { errorMessage, requestError, WORKFLOW_VIEWER_PAGE_SIZE } from "./workflowViewerUtils";

interface ResultPagination {
	frame: Frame;
	cursors: readonly (string | null)[];
	pageIndex: number;
}

export interface InstanceResultsState {
	queryStatus: QueryStatus;
	results: InstanceResultsModel["results"];
	applyFrame: (frame: Frame) => void;
	refreshInstanceResults: InstanceResultsModel["refreshInstanceResults"];
	loadPreviousInstancePage: InstanceResultsModel["loadPreviousInstancePage"];
	loadNextInstancePage: InstanceResultsModel["loadNextInstancePage"];
	resetInstanceResults: () => void;
}

export function useInstanceResults(): InstanceResultsState {
	const [queryStatus, setQueryStatus] = useState<QueryStatus>({ status: "idle" });
	const [results, setResults] = useState<InstanceResultsModel["results"]>({ status: "idle" });
	const [pagination, setPagination] = useState<ResultPagination | null>(null);
	const activeRequest = useRef<AbortController | null>(null);

	const resetInstanceResults = useCallback(() => {
		activeRequest.current?.abort();
		activeRequest.current = null;
		setQueryStatus({ status: "idle" });
		setResults({ status: "idle" });
		setPagination(null);
	}, []);

	useEffect(() => resetInstanceResults, [resetInstanceResults]);

	function runQuery(frame: Frame, cursor: string | null, nextPagination: ResultPagination) {
		activeRequest.current?.abort();
		const controller = new AbortController();
		activeRequest.current = controller;
		setQueryStatus({ status: "submitting" });
		setResults({ status: "loading" });
		void readInstancesAdvancedFiltersInstancesQueryPost(
			{ frame, cursor, limit: WORKFLOW_VIEWER_PAGE_SIZE },
			{ signal: controller.signal },
		)
			.then((response) => {
				if (controller.signal.aborted) return;
				if (response.status !== 200) {
					const message = requestError("Querying instances", response.status);
					setQueryStatus({ status: "error", message });
					setResults({ status: "error", message });
					return;
				}
				setQueryStatus({ status: "idle" });
				setPagination(nextPagination);
				setResults({
					status: "ready",
					data: {
						items: response.data,
						start:
							response.data.length === 0
								? 0
								: nextPagination.pageIndex * WORKFLOW_VIEWER_PAGE_SIZE + 1,
						end:
							nextPagination.pageIndex * WORKFLOW_VIEWER_PAGE_SIZE +
							response.data.length,
						hasPrevious: nextPagination.pageIndex > 0,
						hasNext: response.data.length === WORKFLOW_VIEWER_PAGE_SIZE,
					},
				});
			})
			.catch((error: unknown) => {
				if (controller.signal.aborted) return;
				const message = errorMessage(error);
				setQueryStatus({ status: "error", message });
				setResults({ status: "error", message });
			});
	}

	function applyFrame(frame: Frame) {
		runQuery(frame, null, { frame, cursors: [null], pageIndex: 0 });
	}

	function loadNextInstancePage() {
		if (!pagination || results.status !== "ready") return;
		const last = results.data.items.at(-1);
		if (!last) return;
		const cursor = last.instance.instanceId;
		const cursors = [...pagination.cursors.slice(0, pagination.pageIndex + 1), cursor];
		const nextPagination = {
			frame: pagination.frame,
			cursors,
			pageIndex: pagination.pageIndex + 1,
		};
		runQuery(nextPagination.frame, cursor, nextPagination);
	}

	function loadPreviousInstancePage() {
		if (!pagination || pagination.pageIndex === 0) return;
		const pageIndex = pagination.pageIndex - 1;
		const cursor = pagination.cursors[pageIndex] ?? null;
		runQuery(pagination.frame, cursor, { ...pagination, pageIndex });
	}

	function refreshInstanceResults() {
		if (!pagination) return;
		const cursor = pagination.cursors[pagination.pageIndex] ?? null;
		runQuery(pagination.frame, cursor, pagination);
	}

	return {
		queryStatus,
		results,
		applyFrame,
		refreshInstanceResults,
		loadPreviousInstancePage,
		loadNextInstancePage,
		resetInstanceResults,
	};
}
