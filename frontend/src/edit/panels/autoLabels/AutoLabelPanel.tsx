import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import { ChevronRight } from "lucide-react";
import type { CProvId, ProvChapter, LGProvId } from "../../controller/types/idTypes";
import type { useAutoLabelState } from "../../hooks/useAutoLabelState";
import type { LabelGroupView } from "../../hooks/useTrackedLabelGroups";
import type { AutoLabelManager } from "../../managers/autolabelManager";
import { AutoLabelRunsPanel } from "./AutoLabelRunsPanel";
import { CreateAutoLabelPanel } from "./CreateAutoLabelPanel";
import { PromoteAutoLabelPanel } from "./PromoteAutoLabelPanel";

function AutoLabelSection({
	title,
	defaultOpen = true,
	children,
}: {
	title: string;
	defaultOpen?: boolean;
	children: ReactNode;
}) {
	const [open, setOpen] = useState(defaultOpen);

	return (
		<Collapsible open={open} onOpenChange={setOpen} className="rounded-md border border-border">
			<div className="flex items-center border-b border-border px-2 py-1">
				<CollapsibleTrigger asChild>
					<Button
						type="button"
						variant="ghost"
						size="xs"
						className="min-w-0 flex-1 justify-start"
					>
						<ChevronRight
							data-icon="inline-start"
							className={cn("transition-transform", open && "rotate-90")}
						/>
						{title}
					</Button>
				</CollapsibleTrigger>
			</div>
			<CollapsibleContent>{children}</CollapsibleContent>
		</Collapsible>
	);
}

export function AutoLabelPanel({
	autoLabels,
	autoLabelManager,
	chapters,
	currentChapterId,
	labelGroups,
	onSetActiveLabelGroup,
	previewEnabled,
	previewLoading,
	onSetPreviewEnabled,
}: {
	autoLabels: ReturnType<typeof useAutoLabelState>;
	autoLabelManager: AutoLabelManager;
	chapters: ProvChapter[];
	currentChapterId: CProvId | null;
	labelGroups: [LGProvId, LabelGroupView][];
	onSetActiveLabelGroup: (id: LGProvId | null) => void;
	previewEnabled: boolean;
	previewLoading: boolean;
	onSetPreviewEnabled: AutoLabelManager["setPreviewEnabled"];
}) {
	return (
		<div className="flex h-full min-h-0 flex-col gap-2 overflow-y-auto p-2">
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
			<AutoLabelSection title="Create Auto Labels">
				<CreateAutoLabelPanel
					onCreateRun={autoLabelManager.createRun}
					disabled={autoLabels.refreshing || autoLabels.promoting}
				/>
			</AutoLabelSection>
			<AutoLabelSection title="Runs">
				<AutoLabelRunsPanel
					autoLabels={autoLabels}
					chapters={chapters}
					currentChapterId={currentChapterId}
					onSelectRun={autoLabelManager.selectRun}
					onDeselectRun={autoLabelManager.deselectRun}
					onRefreshAllRuns={autoLabelManager.refreshAllRuns}
					onReloadRun={autoLabelManager.reloadRun}
				/>
			</AutoLabelSection>
			<AutoLabelSection title="Promote">
				<PromoteAutoLabelPanel
					autoLabels={autoLabels}
					labelGroups={labelGroups}
					onSelectRun={autoLabelManager.selectRun}
					onPromote={autoLabelManager.promote}
					onSetActiveLabelGroup={onSetActiveLabelGroup}
				/>
			</AutoLabelSection>
		</div>
	);
}
