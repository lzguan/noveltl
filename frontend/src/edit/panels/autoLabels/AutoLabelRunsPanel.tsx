import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import { ChevronRight, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";
import type { CProvId, ProvChapter } from "../../controller/types/idTypes";
import type { AutoLabelManager } from "../../managers/autolabelManager";
import type {
	AutoLabelRunView,
	AutoLabelView,
	ChapterMatchStatus,
	useAutoLabelState,
} from "../../hooks/useAutoLabelState";
import { formatRunLabel } from "./runLabels";

function statusVariant(status: AutoLabelView["autoLabelStatus"]) {
	if (status === "failed") return "destructive";
	if (status === "done") return "secondary";
	return "outline";
}

function countDone(run: AutoLabelRunView): string {
	if (run.status !== "ready") return "-";
	const done = run.autolabels.filter((al) => al.autoLabelStatus === "done").length;
	return `${done}/${run.autolabels.length}`;
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

function createdAtMs(run: AutoLabelRunView): number {
	const time = new Date(run.run.createdAt).getTime();
	return Number.isNaN(time) ? 0 : time;
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
	run,
	matchMap,
	chapterNumById,
}: {
	run: AutoLabelRunView;
	matchMap: Map<CProvId, ChapterMatchStatus> | undefined;
	chapterNumById: Map<CProvId, number>;
}) {
	if (run.status !== "ready") {
		return (
			<div className="px-2 pb-2 text-xs text-muted-foreground">
				Reload this run to load chapter statuses.
			</div>
		);
	}

	const rows = [...run.autolabels].sort((a, b) => {
		const aNum = chapterNumById.get(a.chapterId) ?? Number.MAX_SAFE_INTEGER;
		const bNum = chapterNumById.get(b.chapterId) ?? Number.MAX_SAFE_INTEGER;
		return aNum - bNum;
	});

	return (
		<div className="flex flex-col gap-1 px-2 pb-2">
			{rows.map((al) => (
				<div key={al.autoLabelId} className="flex items-center gap-1 text-xs">
					<MatchDot status={matchMap?.get(al.chapterId)} />
					<span className="min-w-10 text-muted-foreground">
						Ch. {chapterNumById.get(al.chapterId) ?? "?"}
					</span>
					<Badge variant={statusVariant(al.autoLabelStatus)}>{al.autoLabelStatus}</Badge>
					{al.autoLabelStatus === "done" && (
						<span className="text-muted-foreground">OK</span>
					)}
					{al.autoLabelMessage && (
						<span className="min-w-0 flex-1 truncate text-muted-foreground">
							{al.autoLabelMessage}
						</span>
					)}
				</div>
			))}
		</div>
	);
}

function AutoLabelRunItem({
	run,
	selected,
	matchMap,
	currentStatus,
	chapterNumById,
	onSelectRun,
	onDeselectRun,
	onReloadRun,
}: {
	run: AutoLabelRunView;
	selected: boolean;
	matchMap: Map<CProvId, ChapterMatchStatus> | undefined;
	currentStatus: ChapterMatchStatus | undefined;
	chapterNumById: Map<CProvId, number>;
	onSelectRun: AutoLabelManager["selectRun"];
	onDeselectRun: AutoLabelManager["deselectRun"];
	onReloadRun: AutoLabelManager["reloadRun"];
}) {
	const [expanded, setExpanded] = useState(false);
	const runLabel = formatRunLabel(run);

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
								onSelectRun(run.run.runId);
							}
						}}
					>
						<MatchDot status={currentStatus} />
						<span className="min-w-0 flex-1 truncate">{runLabel}</span>
						<Badge
							variant={
								run.status === "ready"
									? statusVariant(run.overallStatus)
									: "outline"
							}
						>
							{run.status === "ready" ? run.overallStatus : run.status}
						</Badge>
					</button>
					<Button
						type="button"
						size="icon-xs"
						variant="ghost"
						onClick={() => onReloadRun(run.run.runId)}
						aria-label={`Reload ${runLabel}`}
					>
						<RefreshCw />
					</Button>
				</div>
				<div className="px-7 pb-1 text-xs text-muted-foreground">
					{run.run.modelName} · {countDone(run)} done ·{" "}
					{formatCreatedAt(run.run.createdAt)}
				</div>
				<CollapsibleContent>
					<RunRows run={run} matchMap={matchMap} chapterNumById={chapterNumById} />
				</CollapsibleContent>
			</div>
		</Collapsible>
	);
}

export function AutoLabelRunsPanel({
	autoLabels,
	chapters,
	currentChapterId,
	onSelectRun,
	onDeselectRun,
	onRefreshAllRuns,
	onReloadRun,
}: {
	autoLabels: ReturnType<typeof useAutoLabelState>;
	chapters: ProvChapter[];
	currentChapterId: CProvId | null;
	onSelectRun: AutoLabelManager["selectRun"];
	onDeselectRun: AutoLabelManager["deselectRun"];
	onRefreshAllRuns: AutoLabelManager["refreshAllRuns"];
	onReloadRun: AutoLabelManager["reloadRun"];
}) {
	const chapterNumById = useMemo(
		() => new Map(chapters.map((chapter) => [chapter.chapterId, chapter.chapterNum])),
		[chapters],
	);
	const sortedRuns = useMemo(
		() => [...autoLabels.runs].sort((a, b) => createdAtMs(b) - createdAtMs(a)),
		[autoLabels.runs],
	);

	return (
		<section className="flex flex-col gap-1 p-2">
			<div className="flex items-center gap-2 px-1">
				<div className="flex-1" />
				<Button
					type="button"
					size="xs"
					variant="ghost"
					onClick={onRefreshAllRuns}
					disabled={autoLabels.refreshing}
				>
					<RefreshCw data-icon="inline-start" />
					{autoLabels.refreshing ? "Reloading" : "Reload All"}
				</Button>
			</div>
			<div className="flex flex-col gap-1">
				{sortedRuns.length === 0 ? (
					<div className="px-1 py-2 text-xs text-muted-foreground">
						No autolabel runs yet.
					</div>
				) : (
					sortedRuns.map((run) => {
						const selected = autoLabels.selectedRunId === run.run.runId;
						const matchMap = autoLabels.chapterMatchMap.get(run.run.runId);
						const currentStatus = currentChapterId
							? matchMap?.get(currentChapterId)
							: undefined;
						return (
							<AutoLabelRunItem
								key={run.run.runId}
								run={run}
								selected={selected}
								matchMap={matchMap}
								currentStatus={currentStatus}
								chapterNumById={chapterNumById}
								onSelectRun={onSelectRun}
								onDeselectRun={onDeselectRun}
								onReloadRun={onReloadRun}
							/>
						);
					})
				)}
			</div>
		</section>
	);
}
