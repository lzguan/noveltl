import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { toHex } from "@/components/labeled-text-lib/builtin/colors";
import type { LGProvId } from "../controller/types/idTypes";
import type { AddTarget, LabelMeta } from "./types";

/**
 * Form body for creating a label. Presentational and surface-agnostic: it is
 * rendered inside a popover and only collects metadata, calling `onSubmit`.
 */
export function AddLabelForm({
	word,
	targets,
	onSubmit,
	onCancel,
}: {
	word: string;
	targets: AddTarget[];
	onSubmit: (target: LGProvId, meta: LabelMeta) => void;
	onCancel: () => void;
}) {
	const [targetId, setTargetId] = useState<LGProvId | null>(
		targets[0]?.labelGroupId ?? null,
	);
	const [entityGroup, setEntityGroup] = useState("");
	const [score, setScore] = useState("");
	const [dirty, setDirty] = useState(true);

	const handleSubmit = () => {
		if (!targetId) return;
		const parsedScore = score.trim() === "" ? undefined : Number(score);
		onSubmit(targetId, {
			entityGroup: entityGroup.trim() === "" ? undefined : entityGroup.trim(),
			score:
				parsedScore !== undefined && Number.isFinite(parsedScore)
					? parsedScore
					: undefined,
			dirty,
		});
	};

	return (
		<div className="flex flex-col gap-3 text-sm">
			<div className="flex flex-col gap-1">
				<Label className="text-xs text-muted-foreground">Text</Label>
				<div className="truncate rounded border bg-muted/40 px-2 py-1 font-medium">
					{word}
				</div>
			</div>

			{targets.length > 1 ? (
				<div className="flex flex-col gap-1">
					<Label className="text-xs text-muted-foreground">Label group</Label>
					<Select
						value={targetId ?? undefined}
						onValueChange={(value) => {
							const match = targets.find((t) => t.labelGroupId === value);
							if (match) setTargetId(match.labelGroupId);
						}}
					>
						<SelectTrigger className="h-8 w-full">
							<SelectValue placeholder="Select a group" />
						</SelectTrigger>
						<SelectContent>
							{targets.map((t) => (
								<SelectItem key={t.labelGroupId} value={t.labelGroupId}>
									<span
										className="inline-block h-3 w-3 rounded-full"
										style={{ backgroundColor: toHex(t.color) }}
									/>
									{t.groupName}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				</div>
			) : (
				targets[0] && (
					<div className="flex items-center gap-2 text-xs text-muted-foreground">
						<span
							className="h-3 w-3 rounded-full"
							style={{ backgroundColor: toHex(targets[0].color) }}
						/>
						{targets[0].groupName}
					</div>
				)
			)}

			<div className="flex flex-col gap-1">
				<Label htmlFor="lbl-entity" className="text-xs text-muted-foreground">
					Entity group
				</Label>
				<Input
					id="lbl-entity"
					className="h-8"
					placeholder="(optional)"
					value={entityGroup}
					onChange={(e) => setEntityGroup(e.target.value)}
				/>
			</div>

			<div className="flex flex-col gap-1">
				<Label htmlFor="lbl-score" className="text-xs text-muted-foreground">
					Score
				</Label>
				<Input
					id="lbl-score"
					type="number"
					min={0}
					max={1}
					step={0.05}
					className="h-8"
					placeholder="(optional)"
					value={score}
					onChange={(e) => setScore(e.target.value)}
				/>
			</div>

			<Label className="cursor-pointer">
				<Checkbox
					checked={dirty}
					onCheckedChange={(checked) => setDirty(checked === true)}
				/>
				Needs review (dirty)
			</Label>

			<div className="flex justify-end gap-2">
				<Button variant="ghost" size="sm" onClick={onCancel}>
					Cancel
				</Button>
				<Button size="sm" onClick={handleSubmit} disabled={!targetId}>
					Add
				</Button>
			</div>
		</div>
	);
}
