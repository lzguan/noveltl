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
import type { AutoLabelRunView } from "../../hooks/useAutoLabelState";
import type { LabelGroupView } from "../../hooks/useTrackedLabelGroups";
import { formatRunLabel } from "./runLabels";

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
	promoting,
	onPromote,
	onClose,
}: {
	run: AutoLabelRunView;
	labelGroups: [LGProvId, LabelGroupView][];
	defaultLabelGroupId: LGProvId | null;
	promoting: boolean;
	onPromote: (labelGroupId: LGProvId, filter: ChapterFilter) => void;
	onClose: () => void;
}) {
	const [labelGroupId, setLabelGroupId] = useState<LGProvId | null>(
		labelGroups.some(([id]) => id === defaultLabelGroupId) ? defaultLabelGroupId : null,
	);
	const [start, setStart] = useState("");
	const [end, setEnd] = useState("");

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
							disabled={promoting}
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
								disabled={promoting}
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
								disabled={promoting}
								onChange={(event) => setEnd(event.target.value)}
							/>
						</Field>
					</div>
				</FieldGroup>
				<DialogFooter>
					<Button type="button" variant="outline" onClick={onClose}>
						Cancel
					</Button>
					<Button
						type="button"
						disabled={labelGroupId === null || promoting}
						onClick={() => {
							if (labelGroupId === null) return;
							onPromote(labelGroupId, {
								start: parseChapterNum(start),
								end: parseChapterNum(end),
							});
						}}
					>
						{promoting ? "Promoting..." : "Promote"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
