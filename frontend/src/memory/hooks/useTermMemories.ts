import { readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet } from "@/api/endpoints/default/default";
import type { GlossaryMemory } from "@/api/models";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { pageFromOffset, type Loadable, type Page } from "@/lib/loadable";
import { useCallback, useRef, useState } from "react";

export const TERM_MEMORY_PAGE_SIZE = 10;

/** Owns lazy loading and pagination for the memories expanded beneath one glossary term. */
export function useTermMemories(memoryGroupId: string, termId: string, chapterId: string | null) {
	const [skip, setSkip] = useState(0);
	const [memories, setMemories] = useState<Loadable<Page<GlossaryMemory>>>({ status: "idle" });
	const activeRequest = useRef<AbortController | null>(null);
	const skipRef = useRef(0);
	const lastPageRef = useRef<{ itemsLength: number; hasPrevious: boolean } | null>(null);

	const loadPage = useCallback(
		(nextSkip: number) => {
			activeRequest.current?.abort();
			const controller = new AbortController();
			activeRequest.current = controller;
			skipRef.current = nextSkip;
			setSkip(nextSkip);
			setMemories({ status: "loading" });

			void readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet(
				memoryGroupId,
				termId,
				{
					skip: nextSkip,
					limit: TERM_MEMORY_PAGE_SIZE,
					chapterId: chapterId ?? undefined,
				},
				{ signal: controller.signal },
			)
				.then((response) => {
					if (controller.signal.aborted) return;
					if (response.status !== 200) {
						setMemories({
							status: "error",
							message: apiErrorMessage(
								response.data,
								"Could not load term memories.",
							),
						});
						return;
					}
					const data = pageFromOffset(response.data, nextSkip, TERM_MEMORY_PAGE_SIZE);
					lastPageRef.current = {
						itemsLength: data.items.length,
						hasPrevious: data.hasPrevious,
					};
					setMemories({ status: "ready", data });
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
		[chapterId, memoryGroupId, termId],
	);

	const loadMemories = useCallback(() => loadPage(skip), [loadPage, skip]);

	const loadPreviousPage = useCallback(() => {
		if (memories.status !== "ready" || !memories.data.hasPrevious) return;
		loadPage(Math.max(0, skip - TERM_MEMORY_PAGE_SIZE));
	}, [loadPage, memories, skip]);

	const loadNextPage = useCallback(() => {
		if (memories.status !== "ready" || !memories.data.hasNext) return;
		loadPage(skip + TERM_MEMORY_PAGE_SIZE);
	}, [loadPage, memories, skip]);

	const reloadMemoriesAfterDelete = useCallback(() => {
		const lastPage = lastPageRef.current;
		const currentSkip = skipRef.current;
		const nextSkip =
			lastPage !== null && lastPage.itemsLength === 1 && lastPage.hasPrevious
				? Math.max(0, currentSkip - TERM_MEMORY_PAGE_SIZE)
				: currentSkip;
		loadPage(nextSkip);
	}, [loadPage]);

	return {
		memories,
		loadMemories,
		reloadMemories: loadMemories,
		reloadMemoriesAfterDelete,
		loadPreviousPage,
		loadNextPage,
	};
}
