import { readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet } from "@/api/endpoints/default/default";
import type { GlossaryTermSummary } from "@/api/models";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { pageFromOffset, type Loadable, type Page } from "@/lib/loadable";
import { useCallback, useRef, useState } from "react";

export const GLOSSARY_TERM_PAGE_SIZE = 20;

interface GlossaryTermQuery {
	showAllTerms: boolean;
	search: string;
	skip: number;
}

const INITIAL_QUERY: GlossaryTermQuery = {
	showAllTerms: false,
	search: "",
	skip: 0,
};

/** Owns filtering and pagination for the glossary term list. */
export function useGlossaryTerms(memoryGroupId: string, chapterId: string | null) {
	const [query, setQuery] = useState<GlossaryTermQuery>(INITIAL_QUERY);
	const [terms, setTerms] = useState<Loadable<Page<GlossaryTermSummary>>>({ status: "idle" });
	const activeRequest = useRef<AbortController | null>(null);

	const runQuery = useCallback(
		(nextQuery: GlossaryTermQuery) => {
			activeRequest.current?.abort();
			setQuery(nextQuery);

			if (!nextQuery.showAllTerms && chapterId === null) {
				activeRequest.current = null;
				setTerms({ status: "idle" });
				return;
			}

			const controller = new AbortController();
			activeRequest.current = controller;
			setTerms({ status: "loading" });

			void readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet(
				memoryGroupId,
				{
					skip: nextQuery.skip,
					limit: GLOSSARY_TERM_PAGE_SIZE,
					chapterId: nextQuery.showAllTerms ? undefined : chapterId,
					search: nextQuery.search === "" ? undefined : nextQuery.search,
				},
				{ signal: controller.signal },
			)
				.then((response) => {
					if (controller.signal.aborted) return;
					if (response.status !== 200) {
						setTerms({
							status: "error",
							message: apiErrorMessage(
								response.data,
								"Could not load glossary terms.",
							),
						});
						return;
					}
					setTerms({
						status: "ready",
						data: pageFromOffset(
							response.data,
							nextQuery.skip,
							GLOSSARY_TERM_PAGE_SIZE,
						),
					});
				})
				.catch((error: unknown) => {
					if (!controller.signal.aborted) {
						setTerms({ status: "error", message: requestErrorMessage(error) });
					}
				})
				.finally(() => {
					if (activeRequest.current === controller) activeRequest.current = null;
				});
		},
		[chapterId, memoryGroupId],
	);

	const loadTerms = useCallback(() => runQuery(query), [query, runQuery]);

	const setShowAllTerms = useCallback(
		(showAllTerms: boolean) => {
			runQuery({ ...query, showAllTerms, skip: 0 });
		},
		[query, runQuery],
	);

	const setSearch = useCallback(
		(search: string) => {
			runQuery({ ...query, search, skip: 0 });
		},
		[query, runQuery],
	);

	const loadPreviousPage = useCallback(() => {
		if (terms.status !== "ready" || !terms.data.hasPrevious) return;
		runQuery({ ...query, skip: Math.max(0, query.skip - GLOSSARY_TERM_PAGE_SIZE) });
	}, [query, runQuery, terms]);

	const loadNextPage = useCallback(() => {
		if (terms.status !== "ready" || !terms.data.hasNext) return;
		runQuery({ ...query, skip: query.skip + GLOSSARY_TERM_PAGE_SIZE });
	}, [query, runQuery, terms]);

	const reloadTermsAfterDelete = useCallback(() => {
		const nextSkip =
			terms.status === "ready" && terms.data.items.length === 1 && terms.data.hasPrevious
				? Math.max(0, query.skip - GLOSSARY_TERM_PAGE_SIZE)
				: query.skip;
		runQuery({ ...query, skip: nextSkip });
	}, [query, runQuery, terms]);

	return {
		showAllTerms: query.showAllTerms,
		search: query.search,
		terms,
		loadTerms,
		reloadTerms: loadTerms,
		reloadTermsAfterDelete,
		setShowAllTerms,
		setSearch,
		loadPreviousPage,
		loadNextPage,
	};
}
