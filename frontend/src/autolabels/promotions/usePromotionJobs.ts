import { useCallback, useEffect, useEffectEvent, useRef, useState } from "react";
import {
	createLabelPromotionLabelGroupsLabelGroupIdLabelPromotionsPost,
	readLabelPromotionsNovelsNovelIdLabelPromotionsGet,
} from "@/api/endpoints/default/default";
import type { CreateLabelDataByAutoLabel, LabelPromotionJob } from "@/api/models";
import {
	applyPoll,
	applySeed,
	EMPTY_STATE,
	sameState,
	MAX_TRACKED_PROMOTIONS,
	type PromotionJobsState,
} from "./promotionJobsState";

export const PROMOTION_POLL_INTERVAL_MS = 2000;
const MAX_POLL_BACKOFF_MS = 30_000;

export type QueuePromotionResult =
	| { readonly ok: true; readonly promotionId: string; readonly itemCount: number }
	| { readonly ok: false; readonly reason: "tooMany" | "alreadyActive" | "notFound" | "failed" };

type LoopRequest = "none" | "poll" | "reseed";

export function usePromotionJobs({
	novelId,
	onJobFinished,
}: {
	novelId: string | null;
	onJobFinished(job: LabelPromotionJob): void;
}) {
	const [state, setState] = useState<PromotionJobsState>(EMPTY_STATE);
	const [submitting, setSubmitting] = useState(false);
	const stateRef = useRef<PromotionJobsState>(EMPTY_STATE);
	const queuedIdsRef = useRef<string[]>([]);
	const requestRef = useRef<((kind: "poll" | "reseed") => void) | null>(null);
	const commit = useEffectEvent(
		(next: PromotionJobsState, newlyFinished: readonly LabelPromotionJob[]) => {
			if (!sameState(stateRef.current, next)) {
				stateRef.current = next;
				setState(next);
			}
			for (const job of newlyFinished) onJobFinished(job);
		},
	);

	useEffect(() => {
		if (novelId === null) return;

		const abort = new AbortController();
		let pending: LoopRequest = "reseed";
		const noop = () => {};
		let notify = noop;
		let seeded = false;
		let consecutiveFailures = 0;

		// Producers record a request and wake the loop; a reseed supersedes a poll.
		const request = (kind: "poll" | "reseed") => {
			if (pending !== "reseed") pending = kind;
			notify();
		};

		const trackedIds = () =>
			[
				...stateRef.current.active.map((job) => job.promotionId),
				...queuedIdsRef.current,
			].slice(0, MAX_TRACKED_PROMOTIONS);

		const nextDelay = (): number | null => {
			if (seeded && trackedIds().length === 0) return null;
			return Math.min(
				PROMOTION_POLL_INTERVAL_MS * 2 ** consecutiveFailures,
				MAX_POLL_BACKOFF_MS,
			);
		};

		const sleep = (delayMs: number | null) =>
			new Promise<void>((resolve) => {
				const timer = delayMs === null ? null : setTimeout(wake, delayMs);
				function wake() {
					if (timer !== null) clearTimeout(timer);
					notify = noop;
					resolve();
				}
				notify = wake;
			});

		const poll = async () => {
			const requestedIds = trackedIds();
			if (requestedIds.length === 0) return;
			const resp = await readLabelPromotionsNovelsNovelIdLabelPromotionsGet(
				novelId,
				{ promotionIds: requestedIds },
				{ signal: abort.signal },
			);
			if (resp.status !== 200) throw new Error(`Polling promotions failed: ${resp.status}`);
			if (abort.signal.aborted) return;
			const requested = new Set(requestedIds);
			queuedIdsRef.current = queuedIdsRef.current.filter((id) => !requested.has(id));
			const { state: next, newlyFinished } = applyPoll(
				stateRef.current,
				requested,
				resp.data,
			);
			commit(next, newlyFinished);
		};

		const reseed = async () => {
			const resp = await readLabelPromotionsNovelsNovelIdLabelPromotionsGet(
				novelId,
				{ limit: MAX_TRACKED_PROMOTIONS },
				{ signal: abort.signal },
			);
			if (resp.status !== 200) throw new Error(`Loading promotions failed: ${resp.status}`);
			if (abort.signal.aborted) return;
			const seen = new Set(resp.data.map((job) => job.promotionId));
			queuedIdsRef.current = queuedIdsRef.current.filter((id) => !seen.has(id));
			const { state: next, newlyFinished } = applySeed(stateRef.current, resp.data);
			commit(next, newlyFinished);
			seeded = true;
		};

		const run = async () => {
			while (!abort.signal.aborted) {
				if (pending === "none") {
					await sleep(nextDelay());
					if (abort.signal.aborted) return;
					if (pending === "none") pending = seeded ? "poll" : "reseed";
				}
				const kind = pending;
				pending = "none";
				try {
					await (kind === "reseed" ? reseed() : poll());
					consecutiveFailures = 0;
				} catch (error) {
					if (abort.signal.aborted) return;
					consecutiveFailures += 1;
					console.error(`Failed to ${kind} label promotions:`, error);
				}
			}
		};

		requestRef.current = request;
		void run();

		return () => {
			abort.abort();
			notify();
			requestRef.current = null;
			stateRef.current = EMPTY_STATE;
			queuedIdsRef.current = [];
			setState(EMPTY_STATE);
		};
	}, [novelId]);

	const queue = useCallback(
		async (
			labelGroupServId: string,
			request: CreateLabelDataByAutoLabel,
		): Promise<QueuePromotionResult> => {
			if (
				stateRef.current.active.length + queuedIdsRef.current.length >=
				MAX_TRACKED_PROMOTIONS
			) {
				return { ok: false, reason: "tooMany" };
			}
			setSubmitting(true);
			try {
				const resp = await createLabelPromotionLabelGroupsLabelGroupIdLabelPromotionsPost(
					labelGroupServId,
					request,
				);
				if (resp.status === 202) {
					queuedIdsRef.current = [...queuedIdsRef.current, resp.data.promotionId];
					requestRef.current?.("poll");
					return {
						ok: true,
						promotionId: resp.data.promotionId,
						itemCount: resp.data.itemCount,
					};
				}
				if (resp.status === 409) {
					requestRef.current?.("reseed");
					return { ok: false, reason: "alreadyActive" };
				}
				if (resp.status === 404) return { ok: false, reason: "notFound" };
				return { ok: false, reason: "failed" };
			} catch (error) {
				console.error("Failed to queue label promotion:", error);
				return { ok: false, reason: "failed" };
			} finally {
				setSubmitting(false);
			}
		},
		[],
	);

	const refresh = useCallback(() => {
		requestRef.current?.("reseed");
	}, []);

	return {
		jobs: [...state.active, ...state.finished],
		activeCount: state.active.length,
		submitting,
		queue,
		refresh,
	};
}
