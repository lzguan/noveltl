import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ChapterFilter } from "../controller/types/controllerTypes";
import type { AutoLabelManager } from "../managers/autolabelManager";
import { AutoLabelParamsForm, type AutoLabelParamsValue } from "./AutoLabelParamsForm";

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

export function CreateAutoLabelPanel({
	onCreateRun,
	disabled,
}: {
	onCreateRun: AutoLabelManager["createRun"];
	disabled?: boolean;
}) {
	const [params, setParams] = useState<AutoLabelParamsValue>(null);
	const [start, setStart] = useState("");
	const [end, setEnd] = useState("");

	const reset = () => {
		setParams(null);
		setStart("");
		setEnd("");
	};

	return (
		<section className="flex flex-col gap-2 p-2">
			<AutoLabelParamsForm value={params} onChange={setParams} disabled={disabled} />
			<div className="flex flex-col gap-1">
				<Label className="text-xs">Chapters</Label>
				<div className="flex items-center gap-1">
					<Input
						className="h-7 min-w-0 text-xs"
						inputMode="numeric"
						placeholder="Start"
						value={start}
						disabled={disabled}
						onChange={(event) => setStart(event.target.value)}
					/>
					<span className="text-xs text-muted-foreground">to</span>
					<Input
						className="h-7 min-w-0 text-xs"
						inputMode="numeric"
						placeholder="End"
						value={end}
						disabled={disabled}
						onChange={(event) => setEnd(event.target.value)}
					/>
				</div>
			</div>
			<div className="flex justify-end gap-1">
				<Button type="button" size="xs" variant="ghost" onClick={reset} disabled={disabled}>
					Cancel
				</Button>
				<Button
					type="button"
					size="xs"
					disabled={disabled || params === null}
					onClick={() => {
						if (!params) return;
						onCreateRun(params, makeChapterFilter(start, end));
						reset();
					}}
				>
					Create
				</Button>
			</div>
		</section>
	);
}
