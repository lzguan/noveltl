import {
	readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet,
	readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet,
} from "@/api/endpoints/default/default";
import type { Memory, MemoryType } from "@/api/models";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { pageFromOffset, type Loadable, type Page } from "@/lib/loadable";
import { useCallback, useRef, useState } from "react";

export const MEMORY_PAGE_SIZE = 20;

interface MemoryQuery {
	fromAllChapters: boolean;
	memoryType: MemoryType | null;
	skip: number;
}

const INITIAL_QUERY: MemoryQuery = {
	fromAllChapters: false,
	memoryType: null,
	skip: 0,
};

/** Owns filtering and pagination for the View all memories panel. */
export function useMemoryBrowser(memoryGroupId: string, chapterId: string | null) {
	const [query, setQuery] = useState<MemoryQuery>(INITIAL_QUERY);
	const [memories, setMemories] = useState<Loadable<Page<Memory>>>({ status: "idle" });
	const activeRequest = useRef<AbortController | null>(null);

	const runQuery = useCallback(
		(nextQuery: MemoryQuery) => {
			activeRequest.current?.abort();
			setQuery(nextQuery);

			const controller = new AbortController();
			const params = {
				skip: nextQuery.skip,
				limit: MEMORY_PAGE_SIZE,
				memoryTypes: nextQuery.memoryType === null ? undefined : [nextQuery.memoryType],
			};
			let request;
			if (nextQuery.fromAllChapters) {
				request = readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet(memoryGroupId, params, {
					signal: controller.signal,
				});
			} else {
				if (chapterId === null) {
					activeRequest.current = null;
					setMemories({ status: "idle" });
					return;
				}
				request =
					readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet(
						memoryGroupId,
						chapterId,
						params,
						{ signal: controller.signal },
					);
			}

			activeRequest.current = controller;
			setMemories({ status: "loading" });

			void request
				.then((response) => {
					if (controller.signal.aborted) return;
					if (response.status !== 200) {
						setMemories({
							status: "error",
							message: apiErrorMessage(response.data, "Could not load memories."),
						});
						return;
					}
					setMemories({
						status: "ready",
						data: pageFromOffset(response.data, nextQuery.skip, MEMORY_PAGE_SIZE),
					});
				})
				.catch((error: unknown) => {
					if (!controller.signal.aborted) {
						setMemories({ status: "error", message: requestErrorMessage(error) });
					}
				})
				.finally(() => {
					if (activeRequest.current === controller) activeRequest.current = null;
				});
		},
		[chapterId, memoryGroupId],
	);

	const loadMemories = useCallback(() => runQuery(query), [query, runQuery]);

	const setFromAllChapters = useCallback(
		(fromAllChapters: boolean) => {
			runQuery({ ...query, fromAllChapters, skip: 0 });
		},
		[query, runQuery],
	);

	const setMemoryType = useCallback(
		(memoryType: MemoryType | null) => {
			runQuery({ ...query, memoryType, skip: 0 });
		},
		[query, runQuery],
	);

	const loadPreviousPage = useCallback(() => {
		if (memories.status !== "ready" || !memories.data.hasPrevious) return;
		runQuery({ ...query, skip: Math.max(0, query.skip - MEMORY_PAGE_SIZE) });
	}, [memories, query, runQuery]);

	const loadNextPage = useCallback(() => {
		if (memories.status !== "ready" || !memories.data.hasNext) return;
		runQuery({ ...query, skip: query.skip + MEMORY_PAGE_SIZE });
	}, [memories, query, runQuery]);

	return {
		fromAllChapters: query.fromAllChapters,
		memoryType: query.memoryType,
		memories,
		loadMemories,
		reloadMemories: loadMemories,
		setFromAllChapters,
		setMemoryType,
		loadPreviousPage,
		loadNextPage,
	};
}
