import {
	abortMemoryJobMemoryAgentJobsMemoryJobIdAbortPost,
	removeMemoryJobMemoryAgentJobsMemoryJobIdDelete,
	removeMemoryTaskMemoryAgentJobsMemoryJobIdTasksChapterIdDelete,
	retryMemoryTaskMemoryAgentJobsMemoryJobIdTasksChapterIdRetryPost,
	startMemoryJobMemoryAgentJobsMemoryJobIdStartPost,
	startMemoryTaskMemoryAgentJobsMemoryJobIdTasksChapterIdStartPost,
} from "@/api/endpoints/default/default";
import type { MemoryChapterTask, MemoryJobSummary } from "@/api/models";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { useMemoryTasks } from "@/memory/agent/hooks/useMemoryTasks";
import { PageNavigation } from "@/memory/components/PageNavigation";
import {
	CheckCircle2Icon,
	ChevronDownIcon,
	CircleAlertIcon,
	LoaderCircleIcon,
	PlayIcon,
	RefreshCwIcon,
	SquareIcon,
	Trash2Icon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { MemoryTaskRow } from "./MemoryTaskRow";

const TASK_POLL_INTERVAL_MS = 2_500;

type PendingAction =
	| { kind: "start-job" | "abort-job" | "delete-job" }
	| { kind: "start-task" | "retry-task" | "delete-task"; chapterId: string };

type DeleteTarget = { kind: "job" } | { kind: "task"; task: MemoryChapterTask };

export function MemoryJobCard({
	summary,
	claimed,
	expanded,
	watchingDispatch,
	refreshingSummary,
	onExpandedChange,
	onReloadSummary,
	onRemoveJob,
	onWatchDispatch,
}: {
	summary: MemoryJobSummary;
	claimed: boolean;
	expanded: boolean;
	watchingDispatch: boolean;
	refreshingSummary: boolean;
	onExpandedChange: (expanded: boolean) => void;
	onReloadSummary: () => Promise<boolean>;
	onRemoveJob: () => void;
	onWatchDispatch: () => void;
}) {
	const tasks = useMemoryTasks(summary.job.memoryJobId);
	const taskStatus = tasks.tasks.status;
	const tasksRefreshing = tasks.refreshing;
	const reloadTasks = tasks.reloadTasks;
	const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
	const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
	const [actionError, setActionError] = useState<string | null>(null);
	const counts = summary.taskCounts;
	const total = counts.pending + counts.processing + counts.completed + counts.failed;
	const progress = total === 0 ? 0 : Math.round((counts.completed / total) * 100);
	const controlsDisabled = pendingAction !== null || refreshingSummary || tasksRefreshing;
	const canStartJob = !claimed && (counts.pending > 0 || counts.processing > 0);
	const statusLabel = claimed
		? "Running"
		: counts.processing > 0
			? "Interrupted"
			: counts.pending > 0
				? "Ready"
				: counts.failed > 0
					? "Failed"
					: "Complete";

	useEffect(() => {
		if (
			!expanded ||
			(!claimed && !watchingDispatch) ||
			tasksRefreshing ||
			taskStatus !== "ready"
		) {
			return;
		}
		const timeout = window.setTimeout(() => {
			void reloadTasks();
		}, TASK_POLL_INTERVAL_MS);
		return () => window.clearTimeout(timeout);
	}, [claimed, expanded, reloadTasks, taskStatus, tasksRefreshing, watchingDispatch]);

	function changeExpanded(nextExpanded: boolean) {
		onExpandedChange(nextExpanded);
		if (!nextExpanded) {
			tasks.cancelRequest();
			return;
		}
		if (tasks.tasks.status === "idle" || tasks.tasks.status === "error") {
			void tasks.loadTasks();
		} else {
			void tasks.reloadTasks();
		}
	}

	/** Refreshes the aggregate header and the visible task page from one user event. */
	async function refreshJob() {
		const requests: Promise<boolean>[] = [onReloadSummary()];
		if (expanded) requests.push(tasks.reloadTasks());
		await Promise.all(requests);
	}

	async function startJob() {
		setPendingAction({ kind: "start-job" });
		setActionError(null);
		try {
			const response = await startMemoryJobMemoryAgentJobsMemoryJobIdStartPost(
				summary.job.memoryJobId,
			);
			if (response.status !== 202) {
				setActionError(apiErrorMessage(response.data, "Could not start the job."));
				return;
			}
			onWatchDispatch();
			await refreshJob();
		} catch (error) {
			setActionError(requestErrorMessage(error));
		} finally {
			setPendingAction(null);
		}
	}

	async function abortJob() {
		setPendingAction({ kind: "abort-job" });
		setActionError(null);
		try {
			const response = await abortMemoryJobMemoryAgentJobsMemoryJobIdAbortPost(
				summary.job.memoryJobId,
			);
			if (response.status !== 200) {
				setActionError(apiErrorMessage(response.data, "Could not abort the job."));
				return;
			}
			await refreshJob();
		} catch (error) {
			setActionError(requestErrorMessage(error));
		} finally {
			setPendingAction(null);
		}
	}

	async function deleteJob() {
		setPendingAction({ kind: "delete-job" });
		setActionError(null);
		try {
			const response = await removeMemoryJobMemoryAgentJobsMemoryJobIdDelete(
				summary.job.memoryJobId,
			);
			if (response.status !== 204) {
				setActionError(apiErrorMessage(response.data, "Could not delete the job."));
				return;
			}
			onRemoveJob();
			setDeleteTarget(null);
		} catch (error) {
			setActionError(requestErrorMessage(error));
		} finally {
			setPendingAction(null);
		}
	}

	async function startTask(task: MemoryChapterTask) {
		setPendingAction({ kind: "start-task", chapterId: task.chapterId });
		setActionError(null);
		try {
			const response = await startMemoryTaskMemoryAgentJobsMemoryJobIdTasksChapterIdStartPost(
				summary.job.memoryJobId,
				task.chapterId,
			);
			if (response.status !== 202) {
				setActionError(apiErrorMessage(response.data, "Could not start the task."));
				return;
			}
			onWatchDispatch();
			await refreshJob();
		} catch (error) {
			setActionError(requestErrorMessage(error));
		} finally {
			setPendingAction(null);
		}
	}

	async function retryTask(task: MemoryChapterTask) {
		setPendingAction({ kind: "retry-task", chapterId: task.chapterId });
		setActionError(null);
		try {
			const response = await retryMemoryTaskMemoryAgentJobsMemoryJobIdTasksChapterIdRetryPost(
				summary.job.memoryJobId,
				task.chapterId,
			);
			if (response.status !== 202) {
				setActionError(apiErrorMessage(response.data, "Could not retry the task."));
				return;
			}
			onWatchDispatch();
			await refreshJob();
		} catch (error) {
			setActionError(requestErrorMessage(error));
		} finally {
			setPendingAction(null);
		}
	}

	async function deleteTask(task: MemoryChapterTask) {
		setPendingAction({ kind: "delete-task", chapterId: task.chapterId });
		setActionError(null);
		try {
			const response = await removeMemoryTaskMemoryAgentJobsMemoryJobIdTasksChapterIdDelete(
				summary.job.memoryJobId,
				task.chapterId,
			);
			if (response.status !== 204) {
				setActionError(apiErrorMessage(response.data, "Could not delete the task."));
				return;
			}
			await Promise.all([tasks.reloadTasksAfterDelete(), onReloadSummary()]);
			setDeleteTarget(null);
		} catch (error) {
			setActionError(requestErrorMessage(error));
		} finally {
			setPendingAction(null);
		}
	}

	function pendingTaskAction(chapterId: string) {
		if (pendingAction === null || !("chapterId" in pendingAction)) return null;
		if (pendingAction.chapterId !== chapterId) return null;
		if (pendingAction.kind === "start-task") return "start" as const;
		if (pendingAction.kind === "retry-task") return "retry" as const;
		return "delete" as const;
	}

	const createdAt = new Date(summary.job.createdAt).toLocaleString(undefined, {
		dateStyle: "medium",
		timeStyle: "short",
	});

	return (
		<>
			<Collapsible
				open={expanded}
				onOpenChange={changeExpanded}
				className="rounded-lg border bg-card"
			>
				<div className="flex items-start gap-2 p-3">
					<div className="mt-0.5 flex size-7 shrink-0 items-center justify-center">
						{claimed ? (
							<LoaderCircleIcon className="size-5 animate-spin text-primary" />
						) : canStartJob ? (
							<Button
								variant="ghost"
								size="icon-sm"
								aria-label="Start memory-agent job"
								title="Start job"
								disabled={controlsDisabled}
								onClick={() => void startJob()}
							>
								{pendingAction?.kind === "start-job" ? (
									<LoaderCircleIcon className="animate-spin" />
								) : (
									<PlayIcon />
								)}
							</Button>
						) : counts.failed > 0 ? (
							<CircleAlertIcon className="size-5 text-destructive" />
						) : (
							<CheckCircle2Icon className="size-5 text-emerald-600" />
						)}
					</div>

					<CollapsibleTrigger asChild>
						<button type="button" className="min-w-0 flex-1 text-left">
							<div className="flex items-center gap-2">
								<p className="truncate text-sm font-medium">
									Memory agent · {createdAt}
								</p>
								<Badge variant={claimed ? "default" : "outline"}>
									{statusLabel}
								</Badge>
							</div>
							<p className="mt-1 text-xs text-muted-foreground">
								{counts.completed} complete · {counts.pending} pending ·{" "}
								{counts.processing} processing · {counts.failed} failed
							</p>
							<div
								role="progressbar"
								aria-label="Job progress"
								aria-valuemin={0}
								aria-valuemax={total}
								aria-valuenow={counts.completed}
								className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted"
							>
								<div
									className="h-full bg-primary transition-[width]"
									style={{ width: `${progress}%` }}
								/>
							</div>
						</button>
					</CollapsibleTrigger>

					<div className="flex shrink-0 items-center gap-1">
						<Button
							variant="ghost"
							size="icon-sm"
							aria-label="Refresh job"
							title="Refresh job and tasks"
							disabled={controlsDisabled}
							onClick={() => void refreshJob()}
						>
							<RefreshCwIcon
								className={refreshingSummary ? "animate-spin" : undefined}
							/>
						</Button>
						{claimed ? (
							<Button
								variant="destructive"
								size="sm"
								disabled={controlsDisabled}
								onClick={() => void abortJob()}
							>
								{pendingAction?.kind === "abort-job" ? (
									<LoaderCircleIcon className="animate-spin" />
								) : (
									<SquareIcon />
								)}
								Abort
							</Button>
						) : (
							<Button
								variant="ghost"
								size="icon-sm"
								aria-label="Delete job"
								title="Delete job"
								disabled={controlsDisabled}
								onClick={() => setDeleteTarget({ kind: "job" })}
							>
								{pendingAction?.kind === "delete-job" ? (
									<LoaderCircleIcon className="animate-spin" />
								) : (
									<Trash2Icon />
								)}
							</Button>
						)}
						<CollapsibleTrigger asChild>
							<Button
								variant="ghost"
								size="icon-sm"
								aria-label={expanded ? "Collapse job" : "Expand job"}
							>
								<ChevronDownIcon
									className={
										expanded
											? "rotate-180 transition-transform"
											: "transition-transform"
									}
								/>
							</Button>
						</CollapsibleTrigger>
					</div>
				</div>

				<CollapsibleContent>
					<div className="border-t">
						<div className="flex flex-wrap gap-1 border-b px-3 py-2">
							<Badge variant="secondary">{summary.job.jobParams.modelName}</Badge>
							{summary.job.jobParams.plugins.map((plugin) => (
								<Badge key={plugin} variant="outline">
									{plugin}
								</Badge>
							))}
						</div>

						{actionError !== null && (
							<Alert variant="destructive" className="m-2 w-auto">
								<AlertDescription>{actionError}</AlertDescription>
							</Alert>
						)}

						{tasks.tasks.status === "idle" || tasks.tasks.status === "loading" ? (
							<div aria-busy="true" className="flex flex-col gap-2 p-2">
								<Skeleton className="h-12 w-full" />
								<Skeleton className="h-12 w-full" />
							</div>
						) : tasks.tasks.status === "error" ? (
							<div className="flex items-center justify-between gap-2 p-3 text-sm text-destructive">
								<p>{tasks.tasks.message}</p>
								<Button
									variant="outline"
									size="sm"
									onClick={() => void tasks.loadTasks()}
								>
									Retry
								</Button>
							</div>
						) : tasks.tasks.data.items.length === 0 ? (
							<p className="p-3 text-sm text-muted-foreground">
								This job has no chapter tasks.
							</p>
						) : (
							<>
								<div className="divide-y">
									{tasks.tasks.data.items.map((task) => (
										<MemoryTaskRow
											key={task.chapterId}
											task={task}
											jobClaimed={claimed}
											controlsDisabled={controlsDisabled}
											pendingAction={pendingTaskAction(task.chapterId)}
											onStart={() => void startTask(task)}
											onRetry={() => void retryTask(task)}
											onDelete={() => setDeleteTarget({ kind: "task", task })}
										/>
									))}
								</div>
								<PageNavigation
									start={tasks.tasks.data.start}
									end={tasks.tasks.data.end}
									total={tasks.tasks.data.total}
									hasPrevious={tasks.tasks.data.hasPrevious}
									hasNext={tasks.tasks.data.hasNext}
									onPrevious={tasks.loadPreviousPage}
									onNext={tasks.loadNextPage}
								/>
							</>
						)}
					</div>
				</CollapsibleContent>
			</Collapsible>

			{deleteTarget !== null && (
				<Dialog
					open
					onOpenChange={(open) => {
						if (!open && pendingAction === null) setDeleteTarget(null);
					}}
				>
					<DialogContent showCloseButton={pendingAction === null}>
						<DialogHeader>
							<DialogTitle>
								{deleteTarget.kind === "job"
									? "Delete memory-agent job?"
									: "Delete chapter task?"}
							</DialogTitle>
							<DialogDescription>
								{deleteTarget.kind === "job"
									? "This permanently deletes the job and all of its task records. Memories and chapters are not deleted."
									: `This permanently removes chapter ${deleteTarget.task.chapterNum} from this job. The chapter and its memories are not deleted.`}
							</DialogDescription>
						</DialogHeader>
						<DialogFooter>
							<Button
								variant="outline"
								disabled={pendingAction !== null}
								onClick={() => setDeleteTarget(null)}
							>
								Cancel
							</Button>
							<Button
								variant="destructive"
								disabled={pendingAction !== null}
								onClick={() =>
									void (deleteTarget.kind === "job"
										? deleteJob()
										: deleteTask(deleteTarget.task))
								}
							>
								{pendingAction?.kind === "delete-job" ||
								pendingAction?.kind === "delete-task"
									? "Deleting…"
									: "Delete"}
							</Button>
						</DialogFooter>
					</DialogContent>
				</Dialog>
			)}
		</>
	);
}
