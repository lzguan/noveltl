import { useCallback, useEffect, useState } from "react";
import { requestErrorMessage } from "@/lib/apiErrors";

/** Poll sequentially; abort stale pages and retain the last snapshot on refresh errors. */
export function useTranslationRead<T>(load: (signal: AbortSignal) => Promise<T>, invalidation = 0) {
	const [data, setData] = useState<T>();
	const [error, setError] = useState<string>();
	const [refreshing, setRefreshing] = useState(true);
	const [revision, setRevision] = useState(0);
	const refresh = useCallback(() => setRevision((value) => value + 1), []);
	useEffect(() => {
		const controller = new AbortController();
		let timer: ReturnType<typeof setTimeout>;
		async function read() {
			setRefreshing(true);
			try {
				const next = await load(controller.signal);
				if (!controller.signal.aborted) {
					setData(next);
					setError(undefined);
				}
			} catch (error: unknown) {
				if (!controller.signal.aborted) setError(requestErrorMessage(error));
			} finally {
				if (!controller.signal.aborted) {
					setRefreshing(false);
					timer = setTimeout(() => {
						void read();
					}, 5000);
				}
			}
		}
		void read();
		return () => {
			controller.abort();
			clearTimeout(timer);
		};
	}, [load, revision, invalidation]);
	return { data, error, refreshing, refresh };
}
