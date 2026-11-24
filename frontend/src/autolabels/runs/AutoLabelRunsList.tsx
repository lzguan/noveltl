import { ChevronRight, EllipsisIcon, RefreshCw } from "lucide-react";
import { useState } from "react";
import type { AutoLabelProgress, AutoLabelRun } from "@/api/models";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import {
	formatRunLabel,
	getChapterMatchStatus,
	type AutoLabelRunEntry,
	type ChapterMatchStatus,
} from "./autoLabelRunsState";

function statusVariant(status: AutoLabelProgress) {
	if (status === "failed") return "destructive";
	if (status === "done") return "secondary";
	return "outline";
}

function countDone(entry: AutoLabelRunEntry): string {
	if (entry.status !== "ready") return "-";
	const done = entry.autolabels.filter(
		(al) => al.autoLabelMeta.autoLabelStatus === "done",
	).length;
	return `${done}/${entry.autolabels.length}`;
}

function formatCreatedAt(value: string): string {
	const date = new Date(value);
	if (Number.isNaN(date.getTime())) return value;
	return date.toLocaleString(undefined, {
		month: "short",
		day: "numeric",
		hour: "numeric",
		minute: "2-digit",
	});
}

function MatchDot({ status }: { status: ChapterMatchStatus | undefined }) {
	if (!status) return <span className="size-2 shrink-0" aria-hidden="true" />;
	return (
		<span
			className={cn(
				"size-2 shrink-0 rounded-full",
				status === "match" ? "bg-primary" : "border border-muted-foreground",
			)}
			title={status === "match" ? "Current chapter matches" : "Current chapter is outdated"}
		/>
	);
}

function RunRows({
	entry,
	openChapterContentIds,
	chapterNumById,
}: {
	entry: AutoLabelRunEntry;
	openChapterContentIds: ReadonlyMap<string, string | null>;
	chapterNumById: ReadonlyMap<string, number>;
}) {
	if (entry.status === "loading") {
		return (
			<div className="px-2 pb-2 text-xs text-muted-foreground">
				Loading chapter statuses...
			</div>
		);
	}
	if (entry.status === "error") {
		return (
			<div className="px-2 pb-2 text-xs text-destructive">
				Failed to load chapter statuses. Reload to retry.
			</div>
		);
	}
	if (entry.status !== "ready") {
		return (
			<div className="px-2 pb-2 text-xs text-muted-foreground">
				Reload this run to load chapter statuses.
			</div>
		);
	}

	const rows = [...entry.autolabels].sort((a, b) => {
		const aNum = chapterNumById.get(a.chapterId) ?? Number.MAX_SAFE_INTEGER;
		const bNum = chapterNumById.get(b.chapterId) ?? Number.MAX_SAFE_INTEGER;
		return aNum - bNum;
	});

	return (
		<div className="flex flex-col gap-1 px-2 pb-2">
			{rows.map((al) => (
				<div key={al.autoLabelMeta.autoLabelId} className="flex items-center gap-1 text-xs">
					<MatchDot
						status={getChapterMatchStatus(
							al.chapterId,
							al.autoLabelMeta.chapterContentId,
							openChapterContentIds,
						)}
					/>
					<span className="min-w-10 text-muted-foreground">
						Ch. {chapterNumById.get(al.chapterId) ?? "?"}
					</span>
					<Badge variant={statusVariant(al.autoLabelMeta.autoLabelStatus)}>
						{al.autoLabelMeta.autoLabelStatus}
					</Badge>
					{al.autoLabelMeta.autoLabelStatus === "done" && (
						<span className="text-muted-foreground">OK</span>
					)}
					{al.autoLabelMeta.autoLabelMessage && (
						<span className="min-w-0 flex-1 truncate text-muted-foreground">
							{al.autoLabelMeta.autoLabelMessage}
						</span>
					)}
				</div>
			))}
		</div>
	);
}

function AutoLabelRunItem({
	entry,
	selected,
	currentStatus,
	openChapterContentIds,
	chapterNumById,
	onSelectRun,
	onDeselectRun,
	onReloadRun,
	promoteDisabled,
	onPromote,
}: {
	entry: AutoLabelRunEntry;
	selected: boolean;
	currentStatus: ChapterMatchStatus | undefined;
	openChapterContentIds: ReadonlyMap<string, string | null>;
	chapterNumById: ReadonlyMap<string, number>;
	onSelectRun: (runId: string) => void;
	onDeselectRun: () => void;
	onReloadRun: (runId: string) => void;
	promoteDisabled: boolean;
	onPromote: () => void;
}) {
	const [expanded, setExpanded] = useState(false);
	const runLabel = formatRunLabel(entry.run);

	return (
		<Collapsible open={expanded} onOpenChange={setExpanded}>
			<div
				className={cn(
					"rounded-md border border-transparent",
					selected && "border-border bg-muted/40",
				)}
			>
				<div className="flex items-center gap-1">
					<CollapsibleTrigger asChild>
						<Button
							type="button"
							size="icon-xs"
							variant="ghost"
							aria-label={`${expanded ? "Collapse" : "Expand"} ${runLabel}`}
						>
							<ChevronRight
								className={cn("transition-transform", expanded && "rotate-90")}
							/>
						</Button>
					</CollapsibleTrigger>
					<button
						type="button"
						aria-pressed={selected}
						className="flex min-w-0 flex-1 items-center gap-1 rounded-md px-1.5 py-1 text-left text-xs hover:bg-muted"
						onClick={() => {
							if (selected) {
								onDeselectRun();
							} else {
								onSelectRun(entry.run.runId);
							}
						}}
					>
						<MatchDot status={currentStatus} />
						<span className="min-w-0 flex-1 truncate">{runLabel}</span>
						<Badge
							variant={
								entry.status === "ready"
									? statusVariant(entry.overallStatus)
									: "outline"
							}
						>
							{entry.status === "ready" ? entry.overallStatus : entry.status}
						</Badge>
					</button>
					<Button
						type="button"
						size="icon-xs"
						variant="ghost"
						onClick={() => onReloadRun(entry.run.runId)}
						aria-label={`Reload ${runLabel}`}
					>
						<RefreshCw />
					</Button>
					<DropdownMenu>
						<DropdownMenuTrigger asChild>
							<Button
								type="button"
								size="icon-xs"
								variant="ghost"
								aria-label={`More actions for ${runLabel}`}
							>
								<EllipsisIcon />
							</Button>
						</DropdownMenuTrigger>
						<DropdownMenuContent align="end">
							<DropdownMenuItem disabled={promoteDisabled} onSelect={onPromote}>
								Promote…
							</DropdownMenuItem>
						</DropdownMenuContent>
					</DropdownMenu>
				</div>
				<div className="px-7 pb-1 text-xs text-muted-foreground">
					{entry.run.modelName} · {countDone(entry)} done ·{" "}
					{formatCreatedAt(entry.run.createdAt)}
				</div>
				<CollapsibleContent>
					<RunRows
						entry={entry}
						openChapterContentIds={openChapterContentIds}
						chapterNumById={chapterNumById}
					/>
				</CollapsibleContent>
			</div>
		</Collapsible>
	);
}

export function AutoLabelRunsList({
	runs,
	selectedRunId,
	refreshing,
	chapterNumById,
	openChapterContentIds,
	currentChapterId,
	onSelectRun,
	onDeselectRun,
	onRefreshAllRuns,
	onReloadRun,
	canPromote,
	onPromoteRun,
}: {
	runs: readonly AutoLabelRunEntry[];
	selectedRunId: string | null;
	refreshing: boolean;
	chapterNumById: ReadonlyMap<string, number>;
	openChapterContentIds: ReadonlyMap<string, string | null>;
	currentChapterId: string | null;
	onSelectRun: (runId: string) => void;
	onDeselectRun: () => void;
	onRefreshAllRuns: () => void;
	onReloadRun: (runId: string) => void;
	canPromote: boolean;
	onPromoteRun: (run: AutoLabelRun) => void;
}) {
	return (
		<section className="flex flex-col gap-1 p-2">
			<div className="flex items-center gap-2 px-1">
				<div className="flex-1" />
				<Button
					type="button"
					size="xs"
					variant="ghost"
					onClick={onRefreshAllRuns}
					disabled={refreshing}
				>
					<RefreshCw data-icon="inline-start" />
					{refreshing ? "Reloading" : "Reload All"}
				</Button>
			</div>
			<div className="flex flex-col gap-1">
				{runs.length === 0 ? (
					<div className="px-1 py-2 text-xs text-muted-foreground">
						No autolabel runs yet.
					</div>
				) : (
					runs.map((entry) => {
						const selected = selectedRunId === entry.run.runId;
						const currentAutoLabel =
							currentChapterId !== null && entry.status === "ready"
								? entry.autolabels.find((al) => al.chapterId === currentChapterId)
								: undefined;
						const currentStatus = currentAutoLabel
							? getChapterMatchStatus(
									currentAutoLabel.chapterId,
									currentAutoLabel.autoLabelMeta.chapterContentId,
									openChapterContentIds,
								)
							: undefined;
						return (
							<AutoLabelRunItem
								key={entry.run.runId}
								entry={entry}
								selected={selected}
								currentStatus={currentStatus}
								openChapterContentIds={openChapterContentIds}
								chapterNumById={chapterNumById}
								onSelectRun={onSelectRun}
								onDeselectRun={onDeselectRun}
								onReloadRun={onReloadRun}
								promoteDisabled={!canPromote}
								onPromote={() => onPromoteRun(entry.run)}
							/>
						);
					})
				)}
			</div>
		</section>
	);
}
