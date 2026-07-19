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
import type { ChapterFilter } from "../../controller/types/controllerTypes";
import type { AutoLabelManager } from "../../managers/autolabelManager";
import {
	AutoLabelParamsForm,
	type AutoLabelParamModel,
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
	disabled,
}: {
	onCreateRun: AutoLabelManager["createRun"];
	disabled?: boolean;
}) {
	const [params, setParams] = useState<AutoLabelParamsValue>(null);
	const [selectedModel, setSelectedModel] = useState<AutoLabelParamModel | null>(null);
	const [paramsValid, setParamsValid] = useState(true);
	const [advancedOpen, setAdvancedOpen] = useState(false);
	const [start, setStart] = useState("");
	const [end, setEnd] = useState("");

	const reset = () => {
		setParams(null);
		setSelectedModel(null);
		setParamsValid(true);
		setAdvancedOpen(false);
		setStart("");
		setEnd("");
	};

	return (
		<section className="flex flex-col gap-2 p-2">
			<div className="flex flex-col gap-1">
				<Label className="text-xs" htmlFor="autolabel-model">
					Model
				</Label>
				<Select
					value={selectedModel?.name ?? ""}
					disabled={disabled}
					onValueChange={(modelName) => {
						setAdvancedOpen(false);
						setParamsValid(true);
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

			<div className="flex flex-col gap-1">
				<Label className="text-xs">Chapters</Label>
				<div className="flex items-center gap-1">
					<Input
						className="h-7 min-w-0 text-xs"
						inputMode="numeric"
						placeholder="Start"
						aria-label="Start chapter"
						value={start}
						disabled={disabled}
						onChange={(event) => setStart(event.target.value)}
					/>
					<span className="text-xs text-muted-foreground">to</span>
					<Input
						className="h-7 min-w-0 text-xs"
						inputMode="numeric"
						placeholder="End"
						aria-label="End chapter"
						value={end}
						disabled={disabled}
						onChange={(event) => setEnd(event.target.value)}
					/>
				</div>
			</div>

			<Collapsible
				open={advancedOpen}
				onOpenChange={setAdvancedOpen}
				className="rounded-md border border-border"
			>
				<CollapsibleTrigger asChild>
					<Button
						type="button"
						size="xs"
						variant="ghost"
						className="w-full justify-start"
						disabled={
							disabled || !selectedModel || !modelHasAdvancedSettings(selectedModel)
						}
					>
						<ChevronRight
							data-icon="inline-start"
							className={cn("transition-transform", advancedOpen && "rotate-90")}
						/>
						Advanced Settings
					</Button>
				</CollapsibleTrigger>
				<CollapsibleContent className="p-2 pt-0">
					{params && selectedModel && modelHasAdvancedSettings(selectedModel) && (
						<AutoLabelParamsForm
							key={selectedModel.name}
							model={selectedModel}
							value={params}
							onChange={setParams}
							onValidityChange={setParamsValid}
							disabled={disabled}
						/>
					)}
				</CollapsibleContent>
			</Collapsible>

			<div className="flex justify-end gap-1">
				<Button type="button" size="xs" variant="ghost" onClick={reset} disabled={disabled}>
					Cancel
				</Button>
				<Button
					type="button"
					size="xs"
					disabled={disabled || params === null || !paramsValid}
					onClick={() => {
						if (!params || !paramsValid) return;
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
