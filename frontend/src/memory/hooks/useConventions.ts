import { readConventionsMemoryGroupsMemoryGroupIdConventionsGet } from "@/api/endpoints/default/default";
import type { ConventionCategory, ConventionRead } from "@/api/models";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { pageFromOffset, type Loadable, type Page } from "@/lib/loadable";
import { useCallback, useRef, useState } from "react";

export const CONVENTION_PAGE_SIZE = 20;

interface ConventionQuery {
	category: ConventionCategory | null;
	skip: number;
}

const INITIAL_QUERY: ConventionQuery = { category: null, skip: 0 };

/** Owns filtering and pagination for the conventions panel. */
export function useConventions(memoryGroupId: string) {
	const [query, setQuery] = useState<ConventionQuery>(INITIAL_QUERY);
	const [conventions, setConventions] = useState<Loadable<Page<ConventionRead>>>({
		status: "idle",
	});
	const activeRequest = useRef<AbortController | null>(null);
	const latestQueryRef = useRef<ConventionQuery>(INITIAL_QUERY);
	const lastPageRef = useRef<{ itemsLength: number; hasPrevious: boolean } | null>(null);

	const runQuery = useCallback(
		(nextQuery: ConventionQuery) => {
			activeRequest.current?.abort();
			latestQueryRef.current = nextQuery;
			setQuery(nextQuery);

			const controller = new AbortController();
			activeRequest.current = controller;
			setConventions({ status: "loading" });

			void readConventionsMemoryGroupsMemoryGroupIdConventionsGet(
				memoryGroupId,
				{
					skip: nextQuery.skip,
					limit: CONVENTION_PAGE_SIZE,
					category: nextQuery.category ?? undefined,
				},
				{ signal: controller.signal },
			)
				.then((response) => {
					if (controller.signal.aborted) return;
					if (response.status !== 200) {
						setConventions({
							status: "error",
							message: apiErrorMessage(response.data, "Could not load conventions."),
						});
						return;
					}
					const data = pageFromOffset(
						response.data,
						nextQuery.skip,
						CONVENTION_PAGE_SIZE,
					);
					lastPageRef.current = {
						itemsLength: data.items.length,
						hasPrevious: data.hasPrevious,
					};
					setConventions({ status: "ready", data });
				})
				.catch((error: unknown) => {
					if (!controller.signal.aborted) {
						setConventions({ status: "error", message: requestErrorMessage(error) });
					}
				})
				.finally(() => {
					if (activeRequest.current === controller) activeRequest.current = null;
				});
		},
		[memoryGroupId],
	);

	const loadConventions = useCallback(() => runQuery(query), [query, runQuery]);

	const setCategory = useCallback(
		(category: ConventionCategory | null) => {
			runQuery({ ...query, category, skip: 0 });
		},
		[query, runQuery],
	);

	const loadPreviousPage = useCallback(() => {
		if (conventions.status !== "ready" || !conventions.data.hasPrevious) return;
		runQuery({ ...query, skip: Math.max(0, query.skip - CONVENTION_PAGE_SIZE) });
	}, [conventions, query, runQuery]);

	const loadNextPage = useCallback(() => {
		if (conventions.status !== "ready" || !conventions.data.hasNext) return;
		runQuery({ ...query, skip: query.skip + CONVENTION_PAGE_SIZE });
	}, [conventions, query, runQuery]);

	const reloadConventionsAfterDelete = useCallback(() => {
		const latestQuery = latestQueryRef.current;
		const lastPage = lastPageRef.current;
		const nextSkip =
			lastPage !== null && lastPage.itemsLength === 1 && lastPage.hasPrevious
				? Math.max(0, latestQuery.skip - CONVENTION_PAGE_SIZE)
				: latestQuery.skip;
		runQuery({ ...latestQuery, skip: nextSkip });
	}, [runQuery]);

	return {
		category: query.category,
		conventions,
		loadConventions,
		reloadConventions: loadConventions,
		reloadConventionsAfterDelete,
		setCategory,
		loadPreviousPage,
		loadNextPage,
	};
}
