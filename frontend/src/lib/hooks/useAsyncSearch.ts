import { useEffect, useState } from "react";
import type { Loadable } from "../loadable";
import { requestErrorMessage } from "../apiErrors";

export const ASYNC_SEARCH_DEBOUNCE_MS = 250;

export type AsyncSearchFetcher<T> = (keyword: string, signal: AbortSignal) => Promise<readonly T[]>;

export interface AsyncSearchState<T> {
	keyword: string;
	results: Loadable<readonly T[]>;
	setSearchKeyword: (keyword: string) => void;
}

export function useAsyncSearch<T>(
	fetchResults: AsyncSearchFetcher<T>,
	enabled: boolean,
): AsyncSearchState<T> {
	const [keyword, setKeyword] = useState("");
	const normalizedKeyword = keyword.trim();
	const [completedSearch, setCompletedSearch] = useState<{
		fetchResults: AsyncSearchFetcher<T>;
		keyword: string;
		result: { status: "ready"; data: readonly T[] } | { status: "error"; message: string };
	} | null>(null);

	useEffect(() => {
		if (!enabled) return;

		const controller = new AbortController();
		const timeout = window.setTimeout(() => {
			void fetchResults(normalizedKeyword, controller.signal)
				.then((items) => {
					if (!controller.signal.aborted) {
						setCompletedSearch({
							fetchResults,
							keyword: normalizedKeyword,
							result: { status: "ready", data: items },
						});
					}
				})
				.catch((error: unknown) => {
					if (!controller.signal.aborted) {
						setCompletedSearch({
							fetchResults,
							keyword: normalizedKeyword,
							result: { status: "error", message: requestErrorMessage(error) },
						});
					}
				});
		}, ASYNC_SEARCH_DEBOUNCE_MS);

		return () => {
			window.clearTimeout(timeout);
			controller.abort();
		};
	}, [enabled, fetchResults, normalizedKeyword]);

	const results: Loadable<readonly T[]> = !enabled
		? { status: "idle" }
		: completedSearch?.fetchResults === fetchResults &&
			  completedSearch.keyword === normalizedKeyword
			? completedSearch.result
			: { status: "loading" };

	return { keyword, results, setSearchKeyword: setKeyword };
}
