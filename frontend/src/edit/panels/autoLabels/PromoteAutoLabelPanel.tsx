import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import type { ChapterFilter } from "../../controller/types/controllerTypes";
import type { LGProvId } from "../../controller/types/idTypes";
import type { AutoLabelManager } from "../../managers/autolabelManager";
import type { LabelGroupView } from "../../hooks/useTrackedLabelGroups";
import type { useAutoLabelState } from "../../hooks/useAutoLabelState";

function parseChapterNum(value: string): number | undefined {
	const trimmed = value.trim();
	if (!trimmed) return undefined;
	const parsed = Number.parseInt(trimmed, 10);
	return Number.isNaN(parsed) ? undefined : parsed;
}

function makeChapterFilter(start: string, end: string): ChapterFilter {
	return {
		start: parseChapterNum(start),
		end: parseChapterNum(end),
	};
}

function activeLabelGroupId(labelGroups: [LGProvId, LabelGroupView][]): LGProvId | null {
	return labelGroups.find(([, view]) => view.active)?.[0] ?? null;
}

export function PromoteAutoLabelPanel({
	autoLabels,
	labelGroups,
	onSelectRun,
	onPromote,
	onSetActiveLabelGroup,
}: {
	autoLabels: ReturnType<typeof useAutoLabelState>;
	labelGroups: [LGProvId, LabelGroupView][];
	onSelectRun: AutoLabelManager["selectRun"];
	onPromote: AutoLabelManager["promote"];
	onSetActiveLabelGroup: (id: LGProvId | null) => void;
}) {
	const [targetLabelGroupId, setTargetLabelGroupId] = useState<LGProvId | null>(null);
	const [start, setStart] = useState("");
	const [end, setEnd] = useState("");

	useEffect(() => {
		if (targetLabelGroupId !== null) return;
		setTargetLabelGroupId(activeLabelGroupId(labelGroups));
	}, [labelGroups, targetLabelGroupId]);

	const selectedRunId = autoLabels.selectedRunId;
	const canPromote = selectedRunId !== null && targetLabelGroupId !== null && !autoLabels.promoting;

	return (
		<section className="flex flex-col gap-2 p-2">
			<div className="flex items-center gap-1">
				<Select
					value={selectedRunId ?? ""}
					onValueChange={(runId) => {
						const run = autoLabels.runs.find((entry) => entry.run.runId === runId);
						if (run) onSelectRun(run.run.runId);
					}}
					disabled={autoLabels.promoting}
				>
					<SelectTrigger size="sm" className="min-w-0 flex-1">
						<SelectValue placeholder="Run" />
					</SelectTrigger>
					<SelectContent>
						<SelectGroup>
							{autoLabels.runs.map((run) => (
								<SelectItem key={run.run.runId} value={run.run.runId}>
									{run.run.modelName}
								</SelectItem>
							))}
						</SelectGroup>
					</SelectContent>
				</Select>
				<span className="text-xs text-muted-foreground">to</span>
				<Select
					value={targetLabelGroupId ?? ""}
					onValueChange={(labelGroupId) => {
						const match = labelGroups.find(([id]) => id === labelGroupId);
						if (!match) return;
						setTargetLabelGroupId(match[0]);
						onSetActiveLabelGroup(match[0]);
					}}
					disabled={autoLabels.promoting}
				>
					<SelectTrigger size="sm" className="min-w-0 flex-1">
						<SelectValue placeholder="Label group" />
					</SelectTrigger>
					<SelectContent>
						<SelectGroup>
							{labelGroups.map(([id, view]) => (
								<SelectItem key={id} value={id}>
									{view.labelGroup.labelGroupName}
								</SelectItem>
							))}
						</SelectGroup>
					</SelectContent>
				</Select>
			</div>
			<div className="flex flex-col gap-1">
				<Label className="text-xs">Chapters</Label>
				<div className="flex items-center gap-1">
					<Input
						className="h-7 min-w-0 text-xs"
						inputMode="numeric"
						placeholder="Start"
						value={start}
						disabled={autoLabels.promoting}
						onChange={(event) => setStart(event.target.value)}
					/>
					<span className="text-xs text-muted-foreground">to</span>
					<Input
						className="h-7 min-w-0 text-xs"
						inputMode="numeric"
						placeholder="End"
						value={end}
						disabled={autoLabels.promoting}
						onChange={(event) => setEnd(event.target.value)}
					/>
				</div>
			</div>
			<Button
				type="button"
				size="sm"
				disabled={!canPromote}
				onClick={() => {
					if (selectedRunId === null || targetLabelGroupId === null) return;
					onPromote(selectedRunId, targetLabelGroupId, makeChapterFilter(start, end));
				}}
			>
				{autoLabels.promoting ? "Promoting..." : "Promote"}
			</Button>
		</section>
	);
}
