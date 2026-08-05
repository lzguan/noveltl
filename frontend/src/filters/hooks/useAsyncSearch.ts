import { useEffect, useState } from "react";
import type { Loadable } from "../types";
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
	const [results, setResults] = useState<Loadable<readonly T[]>>({ status: "idle" });

	useEffect(() => {
		if (!enabled) {
			setResults({ status: "idle" });
			return;
		}

		const controller = new AbortController();
		setResults({ status: "loading" });
		const timeout = window.setTimeout(() => {
			void fetchResults(keyword.trim(), controller.signal)
				.then((items) => {
					if (!controller.signal.aborted) setResults({ status: "ready", data: items });
				})
				.catch((error: unknown) => {
					if (!controller.signal.aborted)
						setResults({ status: "error", message: requestErrorMessage(error) });
				});
		}, ASYNC_SEARCH_DEBOUNCE_MS);

		return () => {
			window.clearTimeout(timeout);
			controller.abort();
		};
	}, [enabled, fetchResults, keyword]);

	return { keyword, results, setSearchKeyword: setKeyword };
}
