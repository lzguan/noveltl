import { ChevronRight } from "lucide-react";
import { useState } from "react";
import type { LabelPromotionJob } from "@/api/models";
import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

function statusVariant(status: LabelPromotionJob["status"]) {
	if (status === "failed") return "destructive";
	if (status === "done") return "secondary";
	return "outline";
}

function isActive(job: LabelPromotionJob): boolean {
	return job.status === "pending" || job.status === "processing";
}

export function PromotionJobsList({
	jobs,
	runNames,
	labelGroupNames,
}: {
	jobs: readonly LabelPromotionJob[];
	runNames: ReadonlyMap<string, string>;
	labelGroupNames: ReadonlyMap<string, string>;
}) {
	const [open, setOpen] = useState(true);
	if (jobs.length === 0) return null;
	const activeCount = jobs.filter(isActive).length;

	return (
		<Collapsible open={open} onOpenChange={setOpen} className="flex flex-col gap-1 px-2">
			<CollapsibleTrigger className="flex items-center gap-1 rounded-md px-1 py-1 text-left text-xs font-medium text-muted-foreground hover:bg-muted">
				<ChevronRight
					className={cn("size-3.5 transition-transform", open && "rotate-90")}
				/>
				<span className="flex-1">Promotions</span>
				{activeCount > 0 && <Badge variant="outline">{activeCount} running</Badge>}
			</CollapsibleTrigger>
			<CollapsibleContent>
				<ul className="flex flex-col gap-1">
					{jobs.map((job) => {
						const { done, failed, total } = job.counts;
						return (
							<li
								key={job.promotionId}
								className="flex flex-col gap-0.5 rounded-md border border-border px-2 py-1 text-xs"
							>
								<div className="flex items-center gap-1">
									<span className="min-w-0 flex-1 truncate">
										{runNames.get(job.runId) ?? "Unknown run"} →{" "}
										{labelGroupNames.get(job.labelGroupId) ?? "Unknown group"}
									</span>
									<Badge variant={statusVariant(job.status)}>{job.status}</Badge>
								</div>
								<div className="text-muted-foreground">
									{done + failed}/{total} chapters
									{failed > 0 && ` · ${failed} failed`}
									{job.message && ` · ${job.message}`}
								</div>
							</li>
						);
					})}
				</ul>
			</CollapsibleContent>
		</Collapsible>
	);
}
