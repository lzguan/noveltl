import { useCallback, useState } from "react";
import { Info, LoaderCircle, TriangleAlert } from "lucide-react";
import type {
	TranslationJobSummary,
	TranslationProgress,
	TranslationBatchDetail,
} from "@/api/models";
import { listBatchesTranslationJobsJobIdBatchesGet } from "@/api/endpoints/translations/translations";
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
	DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { apiErrorMessage } from "@/lib/apiErrors";
import { useTranslationRead } from "./useTranslationRead";

export type Control = "Start" | "Resume" | "Cancel" | "Retry";
export type ViewerControls = {
	pending: boolean;
	onControl: (jobId: string, control: Control, batchId?: string) => Promise<void>;
};

function Progress({ completed, total }: { completed: number; total: number }) {
	return (
		<div className="flex items-center gap-2">
			<progress
				aria-label="Completed pipeline stages"
				className="h-2 w-full accent-primary"
				value={completed}
				max={total || 1}
			/>
			<span className="text-xs tabular-nums">
				{total ? Math.round((completed / total) * 100) : 0}%
			</span>
		</div>
	);
}
function Controls({
	progress,
	jobId,
	batchId,
	pending,
	onControl,
}: ViewerControls & { progress: TranslationProgress; jobId: string; batchId?: string }) {
	const available = {
		Start: (progress.startableBatches ?? 0) > 0,
		Resume: (progress.resumableBatches ?? 0) > 0,
		Retry: (progress.retryableBatches ?? 0) > 0,
		Cancel:
			(progress.totalTasks ?? 0) > (progress.completedTasks ?? 0) &&
			(progress.totalBatches ?? 0) >
				(progress.completedBatches ?? 0) + (progress.cancelledBatches ?? 0),
	};
	const controls: Control[] = ["Start", "Resume", "Cancel", "Retry"];
	return (
		<div className="flex flex-wrap gap-1">
			{controls.map((control) => (
				<Button
					key={control}
					size="sm"
					variant="outline"
					disabled={pending || !available[control]}
					onClick={() => {
						void onControl(jobId, control, batchId);
					}}
				>
					{control}
				</Button>
			))}
		</div>
	);
}
function state(progress: TranslationProgress) {
	if (!progress.totalTasks) return "No tasks";
	if (progress.completedTasks === progress.totalTasks) return "Complete";
	if (progress.failedBatches) return "Some batches failed";
	if (progress.activeBatches) return "Processing";
	if (progress.cancelledBatches) return "Cancelled batches";
	if (progress.startableBatches === progress.totalBatches) return "Ready to start";
	return "Pending / resumable";
}
export function JobCard({
	job,
	onDetails,
	...controls
}: ViewerControls & { job: TranslationJobSummary; onDetails: () => void }) {
	const progress = job.progress;
	return (
		<article className="rounded-lg border bg-card p-3 space-y-3">
			<div className="flex items-center gap-2">
				<h3 className="mr-auto font-medium">Job {job.jobId.slice(0, 8)}</h3>
				<span className="text-xs">{state(progress)}</span>
				{!!progress.activeBatches && (
					<LoaderCircle aria-label="Processing" className="size-3.5 animate-spin" />
				)}
				{!!progress.failedBatches && (
					<TriangleAlert
						aria-label="Some batches failed"
						className="size-4 text-amber-600"
					/>
				)}
				<Button
					size="icon-sm"
					variant="ghost"
					aria-label={`Show details for job ${job.jobId}`}
					onClick={onDetails}
				>
					<Info />
				</Button>
			</div>
			<p className="text-xs text-muted-foreground">
				{job.stages.length} stages · {progress.totalBatches ?? 0} batches
			</p>
			<Progress completed={progress.completedTasks ?? 0} total={progress.totalTasks ?? 0} />
			<p className="text-xs text-muted-foreground">
				{progress.completedBatches ?? 0} complete · {progress.activeBatches ?? 0} processing
				· {progress.failedBatches ?? 0} failed · {progress.cancelledBatches ?? 0} cancelled
			</p>
			<Controls {...controls} progress={progress} jobId={job.jobId} />
		</article>
	);
}

export function Pagination({
	page,
	total,
	onPage,
}: {
	page: number;
	total: number;
	onPage: (page: number) => void;
}) {
	return (
		<div className="flex items-center justify-between">
			<Button
				size="sm"
				variant="ghost"
				disabled={page === 0}
				onClick={() => onPage(page - 1)}
			>
				Previous
			</Button>
			<span className="text-xs">
				Page {page + 1} · {total} total
			</span>
			<Button
				size="sm"
				variant="ghost"
				disabled={(page + 1) * 5 >= total}
				onClick={() => onPage(page + 1)}
			>
				Next
			</Button>
		</div>
	);
}
function batchProgress(batch: TranslationBatchDetail, observedAt: string): TranslationProgress {
	const unfinished = batch.tasks.filter((task) => task.status !== "complete");
	const failures = unfinished.filter((task) => task.failedAt !== null);
	const live = unfinished.some(
		(task) =>
			task.claimExpiresAt !== null &&
			Date.parse(task.claimExpiresAt) > Date.parse(observedAt),
	);
	const cancelled =
		failures.length > 0 && failures.every((task) => task.error === "Cancelled by user");
	const recoverable = unfinished.length > 0 && !live;
	return {
		totalTasks: batch.tasks.length,
		completedTasks: batch.tasks.length - unfinished.length,
		totalBatches: 1,
		completedBatches: batch.tasks.length > 0 && unfinished.length === 0 ? 1 : 0,
		failedBatches: failures.length > 0 && !cancelled ? 1 : 0,
		cancelledBatches: cancelled ? 1 : 0,
		activeBatches:
			!failures.length && (live || unfinished.some((task) => task.status === "processing"))
				? 1
				: 0,
		startableBatches:
			recoverable && !failures.length && batch.tasks[0]?.status === "ready" ? 1 : 0,
		resumableBatches: recoverable && !failures.length ? 1 : 0,
		retryableBatches: recoverable ? 1 : 0,
	};
}
function BatchPage({
	jobId,
	page,
	revision,
	onPage,
	...controls
}: ViewerControls & {
	jobId: string;
	page: number;
	revision: number;
	onPage: (page: number) => void;
}) {
	const load = useCallback(
		async (signal: AbortSignal) => {
			const response = await listBatchesTranslationJobsJobIdBatchesGet(
				jobId,
				{ offset: page * 5, limit: 5 },
				{ signal },
			);
			if (response.status !== 200)
				throw new Error(apiErrorMessage(response.data, "Could not load batches."));
			return response.data;
		},
		[jobId, page],
	);
	const { data, error, refreshing, refresh } = useTranslationRead(load, revision);
	return (
		<>
			{!data && !error && <p role="status">Loading batches…</p>}
			{error && (
				<p role="alert">
					{error}
					{data && " Showing the last loaded progress."}
				</p>
			)}
			<Button size="sm" variant="outline" disabled={refreshing} onClick={refresh}>
				Reload details
			</Button>
			{data && (
				<>
					<p className="text-xs">
						{data.job.stages
							.map((stage) => stage.action.replaceAll("_", " "))
							.join(" → ")}
					</p>
					<Controls {...controls} progress={data.job.progress} jobId={jobId} />
					{data.items.length === 0 && <p>No batches on this page.</p>}
					{data.items.map((batch) => {
						const progress = batchProgress(batch, data.observedAt);
						return (
							<section
								key={batch.batchId}
								className="rounded-md bg-muted/40 p-3 space-y-2"
							>
								<div className="flex justify-between gap-2 text-sm">
									<h4 className="font-medium">Batch {batch.batchNum + 1}</h4>
									<span>{state(progress)}</span>
								</div>
								<Progress
									completed={progress.completedTasks ?? 0}
									total={progress.totalTasks ?? 0}
								/>
								{batch.tasks.map((task) => (
									<div key={task.taskId} className="text-xs">
										{data.job.stages
											.find((stage) => stage.stageId === task.stageId)
											?.action.replaceAll("_", " ")}{" "}
										· {task.failedAt ? "Failed" : task.status}
										{task.error && (
											<details className="text-destructive">
												<summary>Show error</summary>
												<p className="whitespace-pre-wrap wrap-break-word">
													{task.error}
												</p>
											</details>
										)}
									</div>
								))}
								<Controls
									{...controls}
									progress={progress}
									jobId={jobId}
									batchId={batch.batchId}
								/>
							</section>
						);
					})}
					<Pagination page={page} total={data.total} onPage={onPage} />
				</>
			)}
		</>
	);
}
export function BatchDialog({
	jobId,
	revision,
	notice,
	onClose,
	...controls
}: ViewerControls & { jobId: string; revision: number; notice: string; onClose: () => void }) {
	const [page, setPage] = useState(0);
	return (
		<Dialog
			open
			onOpenChange={(open) => {
				if (!open) onClose();
			}}
		>
			<DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
				<DialogHeader>
					<DialogTitle>Job {jobId.slice(0, 8)} · Batches</DialogTitle>
					<DialogDescription>
						Progress counts completed stages, not individual chapters.
					</DialogDescription>
				</DialogHeader>
				<p className="break-all text-xs text-muted-foreground">{jobId}</p>
				<p role="status" aria-live="polite" className="text-xs">
					{notice}
				</p>
				<BatchPage
					key={page}
					jobId={jobId}
					page={page}
					revision={revision}
					onPage={setPage}
					{...controls}
				/>
			</DialogContent>
		</Dialog>
	);
}
