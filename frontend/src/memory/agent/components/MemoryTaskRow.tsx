import { JobStatus, type MemoryChapterTask } from "@/api/models";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	CheckCircle2Icon,
	Clock3Icon,
	LoaderCircleIcon,
	PlayIcon,
	RotateCcwIcon,
	Trash2Icon,
	TriangleAlertIcon,
} from "lucide-react";

export function MemoryTaskRow({
	task,
	jobClaimed,
	controlsDisabled,
	pendingAction,
	onStart,
	onRetry,
	onDelete,
}: {
	task: MemoryChapterTask;
	jobClaimed: boolean;
	controlsDisabled: boolean;
	pendingAction: "start" | "retry" | "delete" | null;
	onStart: () => void;
	onRetry: () => void;
	onDelete: () => void;
}) {
	return (
		<div className="flex items-center gap-2 border-b px-3 py-2 last:border-b-0">
			<div className="flex size-5 shrink-0 items-center justify-center" aria-hidden="true">
				{task.taskStatus === JobStatus.pending ? (
					jobClaimed ? (
						<Clock3Icon className="size-4 text-muted-foreground" />
					) : (
						<PlayIcon className="size-4 text-muted-foreground" />
					)
				) : task.taskStatus === JobStatus.processing ? (
					jobClaimed ? (
						<LoaderCircleIcon className="size-4 animate-spin text-primary" />
					) : (
						<TriangleAlertIcon className="size-4 text-amber-600" />
					)
				) : task.taskStatus === JobStatus.completed ? (
					<CheckCircle2Icon className="size-4 text-emerald-600" />
				) : (
					<TriangleAlertIcon className="size-4 text-destructive" />
				)}
			</div>

			<div className="min-w-0 flex-1">
				<p className="text-sm font-medium">Chapter {task.chapterNum}</p>
				<p className="text-xs text-muted-foreground">
					{task.taskStatus === JobStatus.pending
						? jobClaimed
							? "Queued"
							: "Pending"
						: task.taskStatus === JobStatus.processing
							? jobClaimed
								? "Running"
								: "Interrupted"
							: task.taskStatus === JobStatus.completed
								? "Complete"
								: `Failed · ${task.attemptCount} ${task.attemptCount === 1 ? "attempt" : "attempts"}`}
				</p>
			</div>

			<div className="flex shrink-0 items-center gap-1">
				{task.taskStatus === JobStatus.pending && !jobClaimed && (
					<Button variant="ghost" size="sm" disabled={controlsDisabled} onClick={onStart}>
						{pendingAction === "start" ? (
							<LoaderCircleIcon className="animate-spin" />
						) : (
							<PlayIcon />
						)}
						Run
					</Button>
				)}
				{task.taskStatus === JobStatus.failed && (
					<Button
						variant="ghost"
						size="sm"
						disabled={controlsDisabled || jobClaimed}
						title={
							jobClaimed
								? "Abort or wait for the current job run before retrying."
								: undefined
						}
						onClick={onRetry}
					>
						{pendingAction === "retry" ? (
							<LoaderCircleIcon className="animate-spin" />
						) : (
							<RotateCcwIcon />
						)}
						Retry
					</Button>
				)}
				{task.taskStatus !== JobStatus.processing && !jobClaimed && (
					<Button
						variant="ghost"
						size="icon-sm"
						aria-label={`Delete chapter ${task.chapterNum} task`}
						title="Delete task"
						disabled={controlsDisabled}
						onClick={onDelete}
					>
						{pendingAction === "delete" ? (
							<LoaderCircleIcon className="animate-spin" />
						) : (
							<Trash2Icon />
						)}
					</Button>
				)}
				{task.taskStatus === JobStatus.completed && <Badge variant="outline">Done</Badge>}
				{task.taskStatus === JobStatus.processing && !jobClaimed && (
					<Badge variant="outline">Resume job</Badge>
				)}
			</div>
		</div>
	);
}
