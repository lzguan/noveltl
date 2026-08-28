import { readMemoryTasksMemoryAgentJobsMemoryJobIdTasksGet } from "@/api/endpoints/default/default";
import type { MemoryChapterTask } from "@/api/models";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { pageFromOffset, type Loadable, type Page } from "@/lib/loadable";
import { useCallback, useRef, useState } from "react";

const MEMORY_TASK_PAGE_SIZE = 20;

/** Owns one job's paginated chapter-task query. */
export function useMemoryTasks(memoryJobId: string) {
	const [skip, setSkip] = useState(0);
	const [tasks, setTasks] = useState<Loadable<Page<MemoryChapterTask>>>({ status: "idle" });
	const [refreshing, setRefreshing] = useState(false);
	const activeRequest = useRef<AbortController | null>(null);
	const lastPageRef = useRef<{ itemsLength: number; hasPrevious: boolean } | null>(null);

	const runQuery = useCallback(
		async (nextSkip: number, preserveData: boolean) => {
			activeRequest.current?.abort();
			const controller = new AbortController();
			activeRequest.current = controller;
			const keepCurrentData = preserveData && tasks.status === "ready";
			setSkip(nextSkip);
			if (keepCurrentData) setRefreshing(true);
			else setTasks({ status: "loading" });

			try {
				const response = await readMemoryTasksMemoryAgentJobsMemoryJobIdTasksGet(
					memoryJobId,
					{ skip: nextSkip, limit: MEMORY_TASK_PAGE_SIZE },
					{ signal: controller.signal },
				);
				if (controller.signal.aborted) return false;
				if (response.status !== 200) {
					setTasks({
						status: "error",
						message: apiErrorMessage(response.data, "Could not load chapter tasks."),
					});
					return false;
				}

				const page = pageFromOffset(response.data, nextSkip, MEMORY_TASK_PAGE_SIZE);
				lastPageRef.current = {
					itemsLength: page.items.length,
					hasPrevious: page.hasPrevious,
				};
				setTasks({ status: "ready", data: page });
				return true;
			} catch (error) {
				if (!controller.signal.aborted) {
					setTasks({ status: "error", message: requestErrorMessage(error) });
				}
				return false;
			} finally {
				if (activeRequest.current === controller) {
					activeRequest.current = null;
					setRefreshing(false);
				}
			}
		},
		[memoryJobId, tasks.status],
	);

	const loadTasks = useCallback(() => runQuery(skip, false), [runQuery, skip]);
	const reloadTasks = useCallback(() => runQuery(skip, true), [runQuery, skip]);

	const loadPreviousPage = useCallback(() => {
		if (tasks.status !== "ready" || !tasks.data.hasPrevious) return;
		void runQuery(Math.max(0, skip - MEMORY_TASK_PAGE_SIZE), false);
	}, [runQuery, skip, tasks]);

	const loadNextPage = useCallback(() => {
		if (tasks.status !== "ready" || !tasks.data.hasNext) return;
		void runQuery(skip + MEMORY_TASK_PAGE_SIZE, false);
	}, [runQuery, skip, tasks]);

	const reloadTasksAfterDelete = useCallback(() => {
		const lastPage = lastPageRef.current;
		const nextSkip =
			lastPage !== null && lastPage.itemsLength === 1 && lastPage.hasPrevious
				? Math.max(0, skip - MEMORY_TASK_PAGE_SIZE)
				: skip;
		return runQuery(nextSkip, true);
	}, [runQuery, skip]);

	const cancelRequest = useCallback(() => {
		activeRequest.current?.abort();
		activeRequest.current = null;
	}, []);

	return {
		tasks,
		refreshing,
		loadTasks,
		reloadTasks,
		reloadTasksAfterDelete,
		loadPreviousPage,
		loadNextPage,
		cancelRequest,
	};
}
