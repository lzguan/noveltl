import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
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
import { cn } from "@/lib/utils";
import type { ChapterFilter } from "./autoLabelRunsState";
import {
	AutoLabelParamsForm,
	type AutoLabelParamModel,
	type AutoLabelParams,
	type AutoLabelParamsValue,
	autoLabelParamModels,
	createAutoLabelParams,
	modelHasAdvancedSettings,
} from "./AutoLabelParamsForm";

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
	submitting = false,
	disabled,
}: {
	onCreateRun: (
		params: AutoLabelParams,
		filter: ChapterFilter,
	) => Promise<string | null> | string | null;
	submitting?: boolean;
	disabled?: boolean;
}) {
	const [params, setParams] = useState<AutoLabelParamsValue>(null);
	const [selectedModel, setSelectedModel] = useState<AutoLabelParamModel | null>(null);
	const [paramsValid, setParamsValid] = useState(true);
	const [advancedOpen, setAdvancedOpen] = useState(false);
	const [start, setStart] = useState("");
	const [end, setEnd] = useState("");
	const [error, setError] = useState<string | null>(null);

	const controlsDisabled = Boolean(disabled) || submitting;

	const reset = () => {
		setParams(null);
		setSelectedModel(null);
		setParamsValid(true);
		setAdvancedOpen(false);
		setStart("");
		setEnd("");
		setError(null);
	};

	return (
		<section className="flex flex-col gap-3">
			<div className="flex flex-col gap-1.5">
				<Label className="text-xs font-medium" htmlFor="autolabel-model">
					Model
				</Label>
				<Select
					value={selectedModel?.name ?? ""}
					disabled={controlsDisabled}
					onValueChange={(modelName) => {
						setAdvancedOpen(false);
						setParamsValid(true);
						setError(null);
						const model = autoLabelParamModels.find(
							(candidate) => candidate.name === modelName,
						);
						if (!model) {
							setSelectedModel(null);
							setParams(null);
							return;
						}
						setSelectedModel(model);
						setParams(createAutoLabelParams(model.name));
					}}
				>
					<SelectTrigger id="autolabel-model" size="sm" className="w-full">
						<SelectValue placeholder="Select a model..." />
					</SelectTrigger>
					<SelectContent>
						<SelectGroup>
							{autoLabelParamModels.map((model) => (
								<SelectItem key={model.name} value={model.name}>
									{model.name}
								</SelectItem>
							))}
						</SelectGroup>
					</SelectContent>
				</Select>
			</div>

			<div className="flex flex-col gap-1.5">
				<Label className="text-xs font-medium">Chapters</Label>
				<div className="flex items-center gap-1.5">
					<Input
						className="h-8 min-w-0 text-xs"
						inputMode="numeric"
						placeholder="Start"
						aria-label="Start chapter"
						value={start}
						disabled={controlsDisabled}
						onChange={(event) => setStart(event.target.value)}
					/>
					<span className="text-xs text-muted-foreground">to</span>
					<Input
						className="h-8 min-w-0 text-xs"
						inputMode="numeric"
						placeholder="End"
						aria-label="End chapter"
						value={end}
						disabled={controlsDisabled}
						onChange={(event) => setEnd(event.target.value)}
					/>
				</div>
			</div>

			<Collapsible
				open={advancedOpen}
				onOpenChange={setAdvancedOpen}
				className="rounded-lg border border-border bg-card"
			>
				<CollapsibleTrigger asChild>
					<Button
						type="button"
						size="sm"
						variant="ghost"
						className="h-8 w-full justify-start px-2.5 text-xs"
						disabled={
							controlsDisabled ||
							!selectedModel ||
							!modelHasAdvancedSettings(selectedModel)
						}
					>
						<ChevronRight
							data-icon="inline-start"
							className={cn("transition-transform", advancedOpen && "rotate-90")}
						/>
						Advanced Settings
					</Button>
				</CollapsibleTrigger>
				<CollapsibleContent className="border-t p-3">
					{params && selectedModel && modelHasAdvancedSettings(selectedModel) && (
						<AutoLabelParamsForm
							key={selectedModel.name}
							model={selectedModel}
							value={params}
							onChange={setParams}
							onValidityChange={setParamsValid}
							disabled={controlsDisabled}
						/>
					)}
				</CollapsibleContent>
			</Collapsible>

			{error !== null && (
				<p role="alert" className="text-xs text-destructive">
					{error}
				</p>
			)}

			<div className="flex justify-end gap-2">
				<Button
					type="button"
					size="sm"
					variant="outline"
					onClick={reset}
					disabled={controlsDisabled}
				>
					Cancel
				</Button>
				<Button
					type="button"
					size="sm"
					disabled={controlsDisabled || params === null || !paramsValid}
					onClick={() => {
						if (!params || !paramsValid || controlsDisabled) return;
						setError(null);
						void Promise.resolve(
							onCreateRun(params, makeChapterFilter(start, end)),
						).then((createError) => {
							if (createError !== null) {
								setError(createError);
								return;
							}
							reset();
						});
					}}
				>
					{submitting ? "Creating..." : "Create"}
				</Button>
			</div>
		</section>
	);
}
