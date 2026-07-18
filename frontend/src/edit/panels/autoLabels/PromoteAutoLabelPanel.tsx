import { useState } from "react";
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
import { formatRunLabel } from "./runLabels";

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


export function PromoteAutoLabelPanel({
	autoLabels,
	labelGroups,
	activeId,
	setActive,
	onSelectRun,
	onPromote,
}: {
	autoLabels: ReturnType<typeof useAutoLabelState>;
	labelGroups: [LGProvId, LabelGroupView][];
	activeId: LGProvId | null;
	setActive: (id: LGProvId | null) => void;
	onSelectRun: AutoLabelManager["selectRun"];
	onPromote: AutoLabelManager["promote"];
}) {
	const [start, setStart] = useState("");
	const [end, setEnd] = useState("");

	const selectedRunId = autoLabels.selectedRunId;
	const canPromote =
		selectedRunId !== null && activeId !== null && !autoLabels.promoting;

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
									{formatRunLabel(run)}
								</SelectItem>
							))}
						</SelectGroup>
					</SelectContent>
				</Select>
				<span className="text-xs text-muted-foreground">to</span>
				<Select
					value={activeId ?? ""}
					onValueChange={(labelGroupId) => {
						const match = labelGroups.find(([id]) => id === labelGroupId);
						if (!match) return;
						setActive(match[0]);
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
					if (selectedRunId === null || activeId === null) return;
					onPromote(selectedRunId, activeId, makeChapterFilter(start, end));
				}}
			>
				{autoLabels.promoting ? "Promoting..." : "Promote"}
			</Button>
		</section>
	);
}
