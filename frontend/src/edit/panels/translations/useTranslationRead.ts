import { useCallback, useEffect, useState } from "react";
import { requestErrorMessage } from "@/lib/apiErrors";
import { useRightPanelTabActive } from "../rightPanelTabActive";

/**
 * Poll sequentially; abort stale pages and retain the last snapshot on refresh errors.
 * Polling pauses while the containing right-panel tab is hidden and reloads when it is shown again.
 */
export function useTranslationRead<T>(load: (signal: AbortSignal) => Promise<T>, invalidation = 0) {
	const [data, setData] = useState<T>();
	const [error, setError] = useState<string>();
	const [refreshing, setRefreshing] = useState(true);
	const [revision, setRevision] = useState(0);
	const refresh = useCallback(() => setRevision((value) => value + 1), []);
	const active = useRightPanelTabActive();
	useEffect(() => {
		if (!active) return;
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
	}, [active, load, revision, invalidation]);
	return { data, error, refreshing, refresh };
}
