import type { LabelPromotionJob } from "@/api/models";

export const MAX_TRACKED_PROMOTIONS = 10;

export type PromotionJobsState = {
	readonly active: readonly LabelPromotionJob[];
	readonly finished: readonly LabelPromotionJob[];
};

export const EMPTY_STATE: PromotionJobsState = { active: [], finished: [] };

function isActive(job: LabelPromotionJob): boolean {
	return job.status === "pending" || job.status === "processing";
}

function byNewest(key: "createdAt" | "updatedAt") {
	return (a: LabelPromotionJob, b: LabelPromotionJob) => Date.parse(b[key]) - Date.parse(a[key]);
}

function arrange(
	active: readonly LabelPromotionJob[],
	finished: readonly LabelPromotionJob[],
): PromotionJobsState {
	const sortedActive = [...active].sort(byNewest("createdAt"));
	const sortedFinished = [...finished]
		.sort(byNewest("updatedAt"))
		.slice(0, Math.max(0, MAX_TRACKED_PROMOTIONS - sortedActive.length));
	return { active: sortedActive, finished: sortedFinished };
}

export function applySeed(
	previous: PromotionJobsState,
	jobs: readonly LabelPromotionJob[],
): { state: PromotionJobsState; newlyFinished: LabelPromotionJob[] } {
	const previouslyActive = new Set(previous.active.map((job) => job.promotionId));
	const finished = jobs.filter((job) => !isActive(job));
	return {
		state: arrange(jobs.filter(isActive), finished),
		newlyFinished: finished.filter((job) => previouslyActive.has(job.promotionId)),
	};
}

export function applyPoll(
	previous: PromotionJobsState,
	requestedIds: ReadonlySet<string>,
	jobs: readonly LabelPromotionJob[],
): { state: PromotionJobsState; newlyFinished: LabelPromotionJob[] } {
	const returned = new Map(jobs.map((job) => [job.promotionId, job]));
	const active: LabelPromotionJob[] = [];
	const newlyFinished: LabelPromotionJob[] = [];
	const place = (job: LabelPromotionJob) => (isActive(job) ? active : newlyFinished).push(job);

	for (const job of previous.active) {
		if (!requestedIds.has(job.promotionId)) {
			active.push(job);
			continue;
		}
		const updated = returned.get(job.promotionId);
		if (updated !== undefined) place(updated);
		returned.delete(job.promotionId);
	}
	// Remaining returned jobs were queued in this session and are seen for the first time.
	for (const job of returned.values()) {
		if (requestedIds.has(job.promotionId)) place(job);
	}

	const newIds = new Set(newlyFinished.map((job) => job.promotionId));
	const finished = [
		...newlyFinished,
		...previous.finished.filter((job) => !newIds.has(job.promotionId)),
	];
	return { state: arrange(active, finished), newlyFinished };
}

function sameJobs(a: readonly LabelPromotionJob[], b: readonly LabelPromotionJob[]): boolean {
	return (
		a.length === b.length &&
		a.every((job, i) => {
			const other = b[i];
			return (
				job.promotionId === other.promotionId &&
				job.status === other.status &&
				job.updatedAt === other.updatedAt &&
				job.message === other.message &&
				job.counts.done === other.counts.done &&
				job.counts.failed === other.counts.failed &&
				job.counts.pending === other.counts.pending
			);
		})
	);
}

export function sameState(a: PromotionJobsState, b: PromotionJobsState): boolean {
	return sameJobs(a.active, b.active) && sameJobs(a.finished, b.finished);
}
