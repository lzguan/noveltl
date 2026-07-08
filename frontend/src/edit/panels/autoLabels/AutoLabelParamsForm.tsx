import { Checkbox } from "@/components/ui/checkbox";
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
import type { CluenerParams, DoNothingParams } from "@/api/models";
import { DoNothingParamsValue, SepPriority } from "@/api/models";

export type AutoLabelParamsValue = CluenerParams | DoNothingParams | null;

const defaultSeparators = {
	"\n": SepPriority.NUMBER_3,
	"。": SepPriority.NUMBER_2,
	"，": SepPriority.NUMBER_1,
};

function makeDefaultCluenerParams(): CluenerParams {
	return {
		modelName: "cluener",
		chunkSize: 500,
		forceChunk: false,
		separators: defaultSeparators,
	};
}

function readModelName(value: AutoLabelParamsValue): "" | "cluener" | "do_nothing" {
	if (!value) return "";
	if (value.modelName === "cluener") return "cluener";
	if (value.modelName === "do_nothing") return "do_nothing";
	return "";
}

function readPriority(value: string) {
	if (value === "1") return SepPriority.NUMBER_1;
	if (value === "3") return SepPriority.NUMBER_3;
	return SepPriority.NUMBER_2;
}

export function AutoLabelParamsForm({
	value,
	onChange,
	disabled,
}: {
	value: AutoLabelParamsValue;
	onChange: (value: AutoLabelParamsValue) => void;
	disabled?: boolean;
}) {
	const modelName = readModelName(value);
	const cluenerParams = value?.modelName === "cluener" ? value : null;
	const separators = cluenerParams?.separators ?? defaultSeparators;

	return (
		<div className="flex flex-col gap-2">
			<div className="flex flex-col gap-1">
				<Label className="text-xs" htmlFor="autolabel-model">
					Model
				</Label>
				<Select
					value={modelName}
					disabled={disabled}
					onValueChange={(next) => {
						if (next === "cluener") {
							onChange(makeDefaultCluenerParams());
						} else if (next === "do_nothing") {
							onChange(DoNothingParamsValue);
						} else {
							onChange(null);
						}
					}}
				>
					<SelectTrigger id="autolabel-model" size="sm" className="w-full">
						<SelectValue placeholder="Select a model..." />
					</SelectTrigger>
					<SelectContent>
						<SelectGroup>
							<SelectItem value="cluener">cluener</SelectItem>
							<SelectItem value="do_nothing">do_nothing</SelectItem>
						</SelectGroup>
					</SelectContent>
				</Select>
			</div>

			{cluenerParams && (
				<div className="flex flex-col gap-2 rounded-md border border-border p-2">
					<div className="flex items-center gap-2">
						<Label className="text-xs flex-1" htmlFor="autolabel-chunk-size">
							Chunk Size
						</Label>
						<Input
							id="autolabel-chunk-size"
							className="h-7 w-20 text-xs"
							type="number"
							min={1}
							max={512}
							value={cluenerParams.chunkSize ?? ""}
							disabled={disabled}
							onChange={(event) => {
								const next = Number.parseInt(event.target.value, 10);
								onChange({
									...cluenerParams,
									chunkSize: Number.isNaN(next) ? undefined : next,
								});
							}}
						/>
					</div>
					<label className="flex items-center gap-2 text-xs">
						<Checkbox
							checked={cluenerParams.forceChunk ?? false}
							disabled={disabled}
							onCheckedChange={(checked) => {
								onChange({
									...cluenerParams,
									forceChunk: checked === true,
								});
							}}
						/>
						<span>Force Chunk</span>
					</label>
					<div className="flex flex-col gap-1">
						<div className="text-xs text-muted-foreground">Separators</div>
						{Object.entries(separators).map(([separator, priority]) => (
							<div key={separator} className="flex items-center gap-1">
								<Input
									className="h-7 min-w-0 flex-1 text-xs"
									value={separator}
									disabled
									aria-label="Separator"
								/>
								<Select
									value={String(priority)}
									disabled={disabled}
									onValueChange={(next) => {
										onChange({
											...cluenerParams,
											separators: {
												...separators,
												[separator]: readPriority(next),
											},
										});
									}}
								>
									<SelectTrigger size="sm" className="h-7 w-20 text-xs">
										<SelectValue />
									</SelectTrigger>
									<SelectContent>
										<SelectGroup>
											<SelectItem value="3">HIGH</SelectItem>
											<SelectItem value="2">MED</SelectItem>
											<SelectItem value="1">LOW</SelectItem>
										</SelectGroup>
									</SelectContent>
								</Select>
							</div>
						))}
					</div>
				</div>
			)}
		</div>
	);
}
