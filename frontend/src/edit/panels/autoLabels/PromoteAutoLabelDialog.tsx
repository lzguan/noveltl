import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
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
import { Switch } from "@/components/ui/switch";
import type { AutoLabelRun } from "@/api/models";
import { formatRunLabel, type ChapterFilter } from "@/autolabels/runs/autoLabelRunsState";
import type { LGProvId } from "../../controller/types/idTypes";
import type { LabelGroupView } from "../../hooks/useTrackedLabelGroups";

function parseChapterNum(value: string): number | undefined {
	const trimmed = value.trim();
	if (!trimmed) return undefined;
	const parsed = Number.parseInt(trimmed, 10);
	return Number.isNaN(parsed) ? undefined : parsed;
}

export function PromoteAutoLabelDialog({
	run,
	labelGroups,
	defaultLabelGroupId,
	submitting,
	onPromote,
	onClose,
}: {
	run: AutoLabelRun;
	labelGroups: [LGProvId, LabelGroupView][];
	defaultLabelGroupId: LGProvId | null;
	submitting: boolean;
	onPromote: (
		labelGroupId: LGProvId,
		filter: ChapterFilter,
		skipExistingLabels: boolean,
	) => Promise<string | null>;
	onClose: () => void;
}) {
	const [labelGroupId, setLabelGroupId] = useState<LGProvId | null>(
		labelGroups.some(([id]) => id === defaultLabelGroupId) ? defaultLabelGroupId : null,
	);
	const [start, setStart] = useState("");
	const [end, setEnd] = useState("");
	const [skipExistingLabels, setSkipExistingLabels] = useState(true);
	const [error, setError] = useState<string | null>(null);

	return (
		<Dialog
			open
			onOpenChange={(open) => {
				if (!open) onClose();
			}}
		>
			<DialogContent className="sm:max-w-md">
				<DialogHeader>
					<DialogTitle>Promote auto labels</DialogTitle>
					<DialogDescription>
						Copy labels from {formatRunLabel(run)} into a label group.
					</DialogDescription>
				</DialogHeader>
				<FieldGroup className="gap-3">
					<Field>
						<FieldLabel htmlFor="promote-label-group">Label group</FieldLabel>
						<Select
							value={labelGroupId ?? ""}
							onValueChange={(value) => {
								const match = labelGroups.find(([id]) => id === value);
								if (match) setLabelGroupId(match[0]);
							}}
							disabled={submitting}
						>
							<SelectTrigger id="promote-label-group" className="w-full">
								<SelectValue placeholder="Choose a label group" />
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
					</Field>
					<div className="grid grid-cols-2 gap-2">
						<Field>
							<FieldLabel htmlFor="promote-start-chapter">Start chapter</FieldLabel>
							<Input
								id="promote-start-chapter"
								inputMode="numeric"
								placeholder="First"
								value={start}
								disabled={submitting}
								onChange={(event) => setStart(event.target.value)}
							/>
						</Field>
						<Field>
							<FieldLabel htmlFor="promote-end-chapter">End chapter</FieldLabel>
							<Input
								id="promote-end-chapter"
								inputMode="numeric"
								placeholder="Last"
								value={end}
								disabled={submitting}
								onChange={(event) => setEnd(event.target.value)}
							/>
						</Field>
					</div>
					<div className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2">
						<div className="flex flex-col gap-0.5">
							<Label
								htmlFor="promote-skip-existing-labels"
								className="text-sm font-medium"
							>
								Skip chapters with existing labels
							</Label>
							<span className="text-xs text-muted-foreground">
								When off, adds non-overlapping labels into chapters that already
								have labels.
							</span>
						</div>
						<Switch
							id="promote-skip-existing-labels"
							checked={skipExistingLabels}
							disabled={submitting}
							onCheckedChange={setSkipExistingLabels}
						/>
					</div>
				</FieldGroup>
				{error !== null && (
					<p role="alert" className="text-xs text-destructive">
						{error}
					</p>
				)}
				<DialogFooter>
					<Button type="button" variant="outline" onClick={onClose}>
						Cancel
					</Button>
					<Button
						type="button"
						disabled={labelGroupId === null || submitting}
						onClick={() => {
							if (labelGroupId === null) return;
							setError(null);
							void onPromote(
								labelGroupId,
								{
									start: parseChapterNum(start),
									end: parseChapterNum(end),
								},
								skipExistingLabels,
							).then(setError);
						}}
					>
						{submitting ? "Starting..." : "Promote"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
