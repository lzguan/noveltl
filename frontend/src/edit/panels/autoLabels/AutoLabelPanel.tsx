import { useMemo, useState } from "react";
import { PromotionJobsList } from "@/autolabels/promotions/PromotionJobsList";
import { MAX_TRACKED_PROMOTIONS } from "@/autolabels/promotions/promotionJobsState";
import {
	type QueuePromotionResult,
	usePromotionJobs,
} from "@/autolabels/promotions/usePromotionJobs";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { ChapterFilter } from "../../controller/types/controllerTypes";
import type { CProvId, ProvChapter, LGProvId } from "../../controller/types/idTypes";
import type { AutoLabelRunView, useAutoLabelState } from "../../hooks/useAutoLabelState";
import type { LabelGroupView } from "../../hooks/useTrackedLabelGroups";
import type { AutoLabelManager } from "../../managers/autolabelManager";
import { AutoLabelRunsPanel } from "./AutoLabelRunsPanel";
import { CreateAutoLabelPanel } from "./CreateAutoLabelPanel";
import { formatRunLabel } from "./runLabels";

const QUEUE_ERRORS: Record<Exclude<QueuePromotionResult, { ok: true }>["reason"], string> = {
	tooMany: `At most ${MAX_TRACKED_PROMOTIONS} promotions can run at once.`,
	alreadyActive: "This run is already being promoted into that label group.",
	notFound: "The run or label group no longer exists, or you cannot edit it.",
	failed: "Could not start the promotion.",
};

type AutoLabelView = "runs" | "create";

function isAutoLabelView(value: string): value is AutoLabelView {
	return value === "runs" || value === "create";
}

export function AutoLabelPanel({
	novelId,
	labelGroupServerId,
	onLabelGroupPromoted,
	autoLabels,
	autoLabelManager,
	chapters,
	currentChapterId,
	labelGroups,
	activeId,
	setActive,
	previewEnabled,
	previewLoading,
	onSetPreviewEnabled,
}: {
	novelId: string;
	labelGroupServerId: (labelGroupId: LGProvId) => string | null;
	onLabelGroupPromoted: (labelGroupServId: string) => void;
	autoLabels: ReturnType<typeof useAutoLabelState>;
	autoLabelManager: AutoLabelManager;
	chapters: ProvChapter[];
	currentChapterId: CProvId | null;
	labelGroups: [LGProvId, LabelGroupView][];
	activeId: LGProvId | null;
	setActive: (id: LGProvId | null) => void;
	previewEnabled: boolean;
	previewLoading: boolean;
	onSetPreviewEnabled: AutoLabelManager["setPreviewEnabled"];
}) {
	const [view, setView] = useState<AutoLabelView>("runs");
	const promotions = usePromotionJobs({
		novelId,
		onJobFinished: (job) => onLabelGroupPromoted(job.labelGroupId),
	});
	const runNames = useMemo(
		() =>
			new Map(
				autoLabels.runs.flatMap((run) =>
					run.run.servId === null ? [] : [[run.run.servId, formatRunLabel(run)] as const],
				),
			),
		[autoLabels.runs],
	);
	// Not memoized: a group's server ID can appear after it syncs without labelGroups changing.
	const labelGroupNames = new Map(
		labelGroups.flatMap(([id, group]) => {
			const servId = labelGroupServerId(id);
			return servId === null ? [] : [[servId, group.labelGroup.labelGroupName] as const];
		}),
	);

	const promote = async (
		run: AutoLabelRunView,
		labelGroupId: LGProvId,
		filter: ChapterFilter,
	): Promise<string | null> => {
		const labelGroupServId = labelGroupServerId(labelGroupId);
		if (run.run.servId === null || labelGroupServId === null) {
			return "This run or label group has not finished saving yet.";
		}
		const result = await promotions.queue(labelGroupServId, {
			runId: run.run.servId,
			start: filter.start ?? null,
			end: filter.end ?? null,
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
				<AutoLabelRunsPanel
					autoLabels={autoLabels}
					chapters={chapters}
					currentChapterId={currentChapterId}
					onSelectRun={autoLabelManager.selectRun}
					onDeselectRun={autoLabelManager.deselectRun}
					onRefreshAllRuns={autoLabelManager.refreshAllRuns}
					onReloadRun={autoLabelManager.reloadRun}
					labelGroups={labelGroups}
					activeId={activeId}
					setActive={setActive}
					promotionSubmitting={promotions.submitting}
					onPromote={promote}
				/>
				<PromotionJobsList
					jobs={promotions.jobs}
					runNames={runNames}
					labelGroupNames={labelGroupNames}
				/>
			</TabsContent>
			{/* Kept mounted so the form keeps its values when switching tabs. */}
			<TabsContent
				value="create"
				forceMount
				hidden={view !== "create"}
				className="min-h-0 flex-1 overflow-y-auto p-2"
			>
				<CreateAutoLabelPanel
					onCreateRun={(params, filter) => {
						autoLabelManager.createRun(params, filter);
						setView("runs");
					}}
					disabled={autoLabels.refreshing}
				/>
			</TabsContent>
		</Tabs>
	);
}
