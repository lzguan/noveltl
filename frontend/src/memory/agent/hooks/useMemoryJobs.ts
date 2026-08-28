import {
	readMemoryJobSummariesMemoryAgentJobSummariesGet,
	readMemoryJobSummaryMemoryAgentJobSummariesMemoryJobIdGet,
} from "@/api/endpoints/default/default";
import type { MemoryJobSummary } from "@/api/models";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import type { Loadable } from "@/lib/loadable";
import { useCallback, useEffect, useRef, useState } from "react";

const JOB_POLL_INTERVAL_MS = 2_500;
const DISPATCH_WATCH_MS = 15_000;

/** Owns memory-agent job summaries, targeted refreshes, and active-job polling. */
export function useMemoryJobs(memoryGroupId: string) {
	const [jobs, setJobs] = useState<Loadable<readonly MemoryJobSummary[]>>({ status: "idle" });
	const [refreshing, setRefreshing] = useState(false);
	const [refreshingJobIds, setRefreshingJobIds] = useState<ReadonlySet<string>>(new Set());
	const [refreshError, setRefreshError] = useState<string | null>(null);
	const [watchingDispatch, setWatchingDispatch] = useState(false);
	const dispatchWatchUntil = useRef(0);
	const activeListRequest = useRef<AbortController | null>(null);
	const activeJobRequests = useRef(new Map<string, AbortController>());

	const runListQuery = useCallback(
		async (preserveData: boolean) => {
			activeListRequest.current?.abort();
			for (const controller of activeJobRequests.current.values()) controller.abort();
			activeJobRequests.current.clear();

			const controller = new AbortController();
			activeListRequest.current = controller;
			const keepCurrentData = preserveData && jobs.status === "ready";
			if (keepCurrentData) setRefreshing(true);
			else setJobs({ status: "loading" });
			setRefreshError(null);

			try {
				const response = await readMemoryJobSummariesMemoryAgentJobSummariesGet(
					{ memoryGroupId },
					{ signal: controller.signal },
				);
				if (controller.signal.aborted) return null;
				if (response.status !== 200) {
					const message = apiErrorMessage(
						response.data,
						"Could not load memory-agent jobs.",
					);
					if (keepCurrentData) setRefreshError(message);
					else setJobs({ status: "error", message });
					return null;
				}

				setJobs({ status: "ready", data: response.data.summaries });
				return response.data.summaries;
			} catch (error) {
				if (controller.signal.aborted) return null;
				const message = requestErrorMessage(error);
				if (keepCurrentData) setRefreshError(message);
				else setJobs({ status: "error", message });
				return null;
			} finally {
				if (activeListRequest.current === controller) {
					activeListRequest.current = null;
					setRefreshing(false);
				}
			}
		},
		[jobs.status, memoryGroupId],
	);

	const loadJobs = useCallback(() => runListQuery(false), [runListQuery]);
	const reloadJobs = useCallback(() => runListQuery(true), [runListQuery]);

	const reloadJob = useCallback(async (memoryJobId: string) => {
		activeJobRequests.current.get(memoryJobId)?.abort();
		const controller = new AbortController();
		activeJobRequests.current.set(memoryJobId, controller);
		setRefreshingJobIds((current) => new Set(current).add(memoryJobId));
		setRefreshError(null);

		try {
			const response = await readMemoryJobSummaryMemoryAgentJobSummariesMemoryJobIdGet(
				memoryJobId,
				{ signal: controller.signal },
			);
			if (controller.signal.aborted) return false;
			if (response.status !== 200) {
				setRefreshError(
					apiErrorMessage(response.data, "Could not refresh the memory-agent job."),
				);
				return false;
			}

			setJobs((current) => {
				if (current.status !== "ready") return current;
				const found = current.data.some(
					(summary) => summary.job.memoryJobId === memoryJobId,
				);
				return {
					status: "ready",
					data: found
						? current.data.map((summary) =>
								summary.job.memoryJobId === memoryJobId
									? response.data.summary
									: summary,
							)
						: [response.data.summary, ...current.data],
				};
			});
			return true;
		} catch (error) {
			if (!controller.signal.aborted) setRefreshError(requestErrorMessage(error));
			return false;
		} finally {
			if (activeJobRequests.current.get(memoryJobId) === controller) {
				activeJobRequests.current.delete(memoryJobId);
				setRefreshingJobIds((current) => {
					const next = new Set(current);
					next.delete(memoryJobId);
					return next;
				});
			}
		}
	}, []);

	const removeJob = useCallback((memoryJobId: string) => {
		setJobs((current) =>
			current.status === "ready"
				? {
						status: "ready",
						data: current.data.filter(
							(summary) => summary.job.memoryJobId !== memoryJobId,
						),
					}
				: current,
		);
	}, []);

	const watchDispatch = useCallback(() => {
		dispatchWatchUntil.current = Math.max(
			dispatchWatchUntil.current,
			Date.now() + DISPATCH_WATCH_MS,
		);
		setWatchingDispatch(true);
	}, []);

	const isClaimed = useCallback((summary: MemoryJobSummary) => summary.isClaimed, []);

	const hasActiveJob = jobs.status === "ready" && jobs.data.some((summary) => isClaimed(summary));

	useEffect(() => {
		if ((!hasActiveJob && !watchingDispatch) || refreshing) return;
		const timeout = window.setTimeout(() => {
			const now = Date.now();
			if (watchingDispatch && now >= dispatchWatchUntil.current) {
				setWatchingDispatch(false);
			}
			void reloadJobs();
		}, JOB_POLL_INTERVAL_MS);
		return () => window.clearTimeout(timeout);
	}, [hasActiveJob, refreshing, reloadJobs, watchingDispatch]);

	const cancelRequests = useCallback(() => {
		activeListRequest.current?.abort();
		for (const controller of activeJobRequests.current.values()) controller.abort();
		activeJobRequests.current.clear();
	}, []);

	return {
		jobs,
		refreshing,
		refreshingJobIds,
		refreshError,
		watchingDispatch,
		loadJobs,
		reloadJobs,
		reloadJob,
		removeJob,
		watchDispatch,
		isClaimed,
		cancelRequests,
	};
}
