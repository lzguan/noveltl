import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { useMemoryJobs } from "@/memory/agent/hooks/useMemoryJobs";
import { PlusIcon, RefreshCwIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { CreateMemoryJobForm } from "./CreateMemoryJobForm";
import { MemoryJobCard } from "./MemoryJobCard";

export function MemoryJobBrowser({ memoryGroupId }: { memoryGroupId: string }) {
	const jobs = useMemoryJobs(memoryGroupId);
	const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
	const [createJobOpen, setCreateJobOpen] = useState(false);

	useEffect(() => {
		void jobs.loadJobs();
		return jobs.cancelRequests;
		// This keyed browser loads once for its memory-group identity.
		// oxlint-disable-next-line react-hooks/exhaustive-deps
	}, []);

	async function jobCreated() {
		await jobs.reloadJobs();
	}

	return (
		<div className="flex min-h-0 flex-1 flex-col">
			<div className="flex items-center justify-between border-b p-2">
				<div>
					<p className="text-sm font-medium">Jobs</p>
					<p className="text-xs text-muted-foreground">Memory-agent chapter runs</p>
				</div>
				<div className="flex items-center gap-1">
					<Button variant="ghost" size="sm" onClick={() => setCreateJobOpen(true)}>
						<PlusIcon /> New job
					</Button>
					<Button
						variant="ghost"
						size="icon-sm"
						aria-label="Refresh all jobs"
						title="Refresh all jobs"
						disabled={jobs.refreshing || jobs.jobs.status === "loading"}
						onClick={() => void jobs.reloadJobs()}
					>
						<RefreshCwIcon className={jobs.refreshing ? "animate-spin" : undefined} />
					</Button>
				</div>
			</div>

			{jobs.refreshError !== null && (
				<Alert variant="destructive" className="m-2 w-auto">
					<AlertDescription>{jobs.refreshError}</AlertDescription>
				</Alert>
			)}

			<div className="min-h-0 flex-1 overflow-y-auto p-2">
				{jobs.jobs.status === "idle" || jobs.jobs.status === "loading" ? (
					<div aria-busy="true" className="flex flex-col gap-2">
						<Skeleton className="h-24 w-full" />
						<Skeleton className="h-24 w-full" />
					</div>
				) : jobs.jobs.status === "error" ? (
					<div className="flex flex-col items-start gap-2 p-2 text-sm text-destructive">
						<p>{jobs.jobs.message}</p>
						<Button variant="outline" size="sm" onClick={() => void jobs.loadJobs()}>
							Retry
						</Button>
					</div>
				) : jobs.jobs.data.length === 0 ? (
					<Empty className="min-h-40 border">
						<EmptyHeader>
							<EmptyTitle>No memory-agent jobs</EmptyTitle>
							<EmptyDescription>
								Create a new job to select its chapter tasks.
							</EmptyDescription>
						</EmptyHeader>
					</Empty>
				) : (
					<div className="flex flex-col gap-2">
						{jobs.jobs.data.map((summary) => {
							const memoryJobId = summary.job.memoryJobId;
							return (
								<MemoryJobCard
									key={memoryJobId}
									summary={summary}
									claimed={jobs.isClaimed(summary)}
									expanded={expandedJobId === memoryJobId}
									watchingDispatch={jobs.watchingDispatch}
									refreshingSummary={jobs.refreshingJobIds.has(memoryJobId)}
									onExpandedChange={(expanded) =>
										setExpandedJobId(expanded ? memoryJobId : null)
									}
									onReloadSummary={() => jobs.reloadJob(memoryJobId)}
									onRemoveJob={() => {
										jobs.removeJob(memoryJobId);
										setExpandedJobId((current) =>
											current === memoryJobId ? null : current,
										);
									}}
									onWatchDispatch={jobs.watchDispatch}
								/>
							);
						})}
					</div>
				)}
			</div>

			{createJobOpen && (
				<CreateMemoryJobForm
					memoryGroupId={memoryGroupId}
					onCreated={jobCreated}
					closeDialog={() => setCreateJobOpen(false)}
				/>
			)}
		</div>
	);
}
