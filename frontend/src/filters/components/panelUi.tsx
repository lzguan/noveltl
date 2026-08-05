import type { GroupingResponse, WorkflowStatus, WorkflowSummary } from "@/api/models";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { Page } from "../types";

export function shortId(value: string) {
	return value.slice(0, 8);
}

export function workflowLabel(workflow: WorkflowSummary) {
	return workflow.workflowName?.trim() || `Untitled workflow · ${shortId(workflow.workflowId)}`;
}

export function groupingLabel(grouping: GroupingResponse) {
	return `${grouping.functionDefinition.namespace}.${grouping.functionDefinition.functionName}`;
}

export function statusVariant(status: WorkflowStatus | GroupingResponse["groupingStatus"]) {
	if (status === "failed") return "destructive";
	if (status === "complete") return "secondary";
	return "outline";
}

export function LoadingBlock() {
	return (
		<div className="flex flex-col gap-2" aria-label="Loading">
			<Skeleton className="h-9 w-full" />
			<Skeleton className="h-9 w-3/4" />
		</div>
	);
}

export function ErrorBlock({ title, message }: { title: string; message: string }) {
	return (
		<Alert variant="destructive">
			<AlertTitle>{title}</AlertTitle>
			<AlertDescription>{message}</AlertDescription>
		</Alert>
	);
}

export function PageControls({
	page,
	label,
	loadPreviousPage,
	loadNextPage,
}: {
	page: Page<unknown>;
	label: string;
	loadPreviousPage: () => void;
	loadNextPage: () => void;
}) {
	const range =
		page.total === undefined
			? `${page.start}–${page.end}`
			: `${page.start}–${page.end} of ${page.total}`;
	return (
		<div className="flex items-center justify-between gap-2">
			<span className="text-sm text-muted-foreground">{range}</span>
			<div className="flex items-center gap-1">
				<Button
					type="button"
					variant="outline"
					size="icon-sm"
					disabled={!page.hasPrevious}
					onClick={loadPreviousPage}
					aria-label={`Previous ${label} page`}
				>
					<ChevronLeft />
				</Button>
				<Button
					type="button"
					variant="outline"
					size="icon-sm"
					disabled={!page.hasNext}
					onClick={loadNextPage}
					aria-label={`Next ${label} page`}
				>
					<ChevronRight />
				</Button>
			</div>
		</div>
	);
}
