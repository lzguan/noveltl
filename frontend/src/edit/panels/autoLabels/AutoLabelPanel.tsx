import { useMemo, useState } from "react";
import type { AutoLabelRun } from "@/api/models";
import { PromotionJobsList } from "@/autolabels/promotions/PromotionJobsList";
import { MAX_TRACKED_PROMOTIONS } from "@/autolabels/promotions/promotionJobsState";
import {
	type QueuePromotionResult,
	usePromotionJobs,
} from "@/autolabels/promotions/usePromotionJobs";
import { AutoLabelRunsList } from "@/autolabels/runs/AutoLabelRunsList";
import {
	formatRunLabel,
	type ChapterFilter,
	type SelectedAutoLabelRun,
} from "@/autolabels/runs/autoLabelRunsState";
import { CreateAutoLabelPanel } from "@/autolabels/runs/CreateAutoLabelPanel";
import {
	type CreateAutoLabelRunResult,
	useAutoLabelRuns,
} from "@/autolabels/runs/useAutoLabelRuns";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { LGProvId } from "../../controller/types/idTypes";
import type { LabelGroupView } from "../../hooks/useTrackedLabelGroups";
import { PromoteAutoLabelDialog } from "./PromoteAutoLabelDialog";

const QUEUE_ERRORS: Record<Exclude<QueuePromotionResult, { ok: true }>["reason"], string> = {
	tooMany: `At most ${MAX_TRACKED_PROMOTIONS} promotions can run at once.`,
	alreadyActive: "This run is already being promoted into that label group.",
	notFound: "The run or label group no longer exists, or you cannot edit it.",
	failed: "Could not start the promotion.",
};

const CREATE_ERRORS: Record<Exclude<CreateAutoLabelRunResult, { ok: true }>["reason"], string> = {
	badRequest: "Invalid autolabel parameters or chapter range.",
	notFound: "This novel was not found, or you cannot run autolabels on it.",
	failed: "Could not start the autolabel run.",
};

type AutoLabelView = "runs" | "create";

function isAutoLabelView(value: string): value is AutoLabelView {
	return value === "runs" || value === "create";
}

export function AutoLabelPanel({
	novelId,
	labelGroupServerId,
	onLabelGroupPromoted,
	chapterNumByServerId,
	currentChapterId,
	openChapterContentIds,
	labelGroups,
	activeId,
	setActive,
	previewEnabled,
	previewLoading,
	onSetPreviewEnabled,
	onSelectedRunChange,
}: {
	novelId: string;
	labelGroupServerId: (labelGroupId: LGProvId) => string | null;
	onLabelGroupPromoted: (labelGroupServId: string) => void;
	chapterNumByServerId: ReadonlyMap<string, number>;
	currentChapterId: string | null;
	openChapterContentIds: ReadonlyMap<string, string | null>;
	labelGroups: [LGProvId, LabelGroupView][];
	activeId: LGProvId | null;
	setActive: (id: LGProvId | null) => void;
	previewEnabled: boolean;
	previewLoading: boolean;
	onSetPreviewEnabled: (enabled: boolean) => void;
	onSelectedRunChange: (selection: SelectedAutoLabelRun) => void;
}) {
	const [view, setView] = useState<AutoLabelView>("runs");
	const [promotingRun, setPromotingRun] = useState<AutoLabelRun | null>(null);
	const runs = useAutoLabelRuns({
		novelId,
		onSelectedRunChange,
	});
	const promotions = usePromotionJobs({
		novelId,
		onJobFinished: (job) => onLabelGroupPromoted(job.labelGroupId),
	});
	const runNames = useMemo(
		() =>
			new Map(
				runs.runs.map((entry) => [entry.run.runId, formatRunLabel(entry.run)] as const),
			),
		[runs.runs],
	);
	// Not memoized: a group's server ID can appear after it syncs without labelGroups changing.
	const labelGroupNames = new Map(
		labelGroups.flatMap(([id, group]) => {
			const servId = labelGroupServerId(id);
			return servId === null ? [] : [[servId, group.labelGroup.labelGroupName] as const];
		}),
	);

	const promote = async (
		run: AutoLabelRun,
		labelGroupId: LGProvId,
		filter: ChapterFilter,
		skipExistingLabels: boolean,
	): Promise<string | null> => {
		const labelGroupServId = labelGroupServerId(labelGroupId);
		if (labelGroupServId === null) {
			return "This label group has not finished saving yet.";
		}
		const result = await promotions.queue(labelGroupServId, {
			runId: run.runId,
			start: filter.start ?? null,
			end: filter.end ?? null,
			skipExistingLabels,
		});
		return result.ok ? null : QUEUE_ERRORS[result.reason];
	};

	return (
		<Tabs
			value={view}
			onValueChange={(value) => {
				if (isAutoLabelView(value)) setView(value);
			}}
			className="h-full min-h-0 gap-0"
		>
			<TabsList
				variant="line"
				className="w-full shrink-0 justify-start border-b px-1 group-data-horizontal/tabs:h-auto"
			>
				<TabsTrigger value="runs" className="flex-none">
					Runs
				</TabsTrigger>
				<TabsTrigger value="create" className="flex-none">
					Create
				</TabsTrigger>
			</TabsList>
			<TabsContent
				value="runs"
				forceMount
				hidden={view !== "runs"}
				className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-2"
			>
				<div className="flex items-center justify-between gap-2 rounded-md border border-border px-2 py-1.5">
					<Label className="text-xs" htmlFor="autolabel-preview-enabled">
						Show selected run preview
					</Label>
					<div className="flex items-center gap-2">
						{previewLoading && (
							<span role="status" className="text-xs text-muted-foreground">
								Loading preview...
							</span>
						)}
						<Switch
							id="autolabel-preview-enabled"
							size="sm"
							checked={previewEnabled}
							onCheckedChange={onSetPreviewEnabled}
						/>
					</div>
				</div>
				<AutoLabelRunsList
					runs={runs.runs}
					selectedRunId={runs.selectedRunId}
					refreshing={runs.refreshing}
					chapterNumById={chapterNumByServerId}
					openChapterContentIds={openChapterContentIds}
					currentChapterId={currentChapterId}
					onSelectRun={runs.selectRun}
					onDeselectRun={runs.deselectRun}
					onRefreshAllRuns={runs.refreshAll}
					onReloadRun={runs.reloadRun}
					canPromote={labelGroups.length > 0}
					onPromoteRun={setPromotingRun}
				/>
				<PromotionJobsList
					jobs={promotions.jobs}
					runNames={runNames}
					labelGroupNames={labelGroupNames}
				/>
				{promotingRun !== null && (
					<PromoteAutoLabelDialog
						run={promotingRun}
						labelGroups={labelGroups}
						defaultLabelGroupId={activeId}
						submitting={promotions.submitting}
						onPromote={async (labelGroupId, filter, skipExistingLabels) => {
							const error = await promote(
								promotingRun,
								labelGroupId,
								filter,
								skipExistingLabels,
							);
							if (error !== null) return error;
							// The chosen group becomes active so its promoted labels are shown.
							setActive(labelGroupId);
							setPromotingRun(null);
							return null;
						}}
						onClose={() => setPromotingRun(null)}
					/>
				)}
			</TabsContent>
			{/* Kept mounted so the form keeps its values when switching tabs. */}
			<TabsContent
				value="create"
				forceMount
				hidden={view !== "create"}
				className="min-h-0 flex-1 overflow-y-auto p-2"
			>
				<CreateAutoLabelPanel
					submitting={runs.creating}
					onCreateRun={async (params, filter) => {
						const result = await runs.createRun(params, filter);
						if (!result.ok) return CREATE_ERRORS[result.reason];
						setView("runs");
						return null;
					}}
				/>
			</TabsContent>
		</Tabs>
	);
}
