import {
	addMemoryJobMemoryAgentJobsPost,
	readMemoryAgentConfigMemoryAgentConfigGet,
} from "@/api/endpoints/default/default";
import type {
	CreateMemoryJob,
	JobParamsToolsets,
	MemoryAgentConfig,
	MemoryAgentToolsetOption,
	ModelName,
} from "@/api/models";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { LoaderCircleIcon, PlaySquareIcon, Settings2Icon } from "lucide-react";
import { useEffect, useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { ToolsetConfigDialog, toolsetHasConfig } from "./ToolsetConfigDialog";

type MemoryJobFormValues = {
	startChapterNum: string;
	endChapterNum: string;
	modelName: ModelName;
	toolsets: JobParamsToolsets;
};

type CreateMemoryJobFormProps = {
	memoryGroupId: string;
	onCreated: (memoryJobId: string) => Promise<void>;
	closeDialog: () => void;
};

function defaultToolsets(config: MemoryAgentConfig): JobParamsToolsets {
	return Object.fromEntries(
		config.toolsets
			.filter((toolset) => toolset.defaultEnabled)
			.map((toolset) => [toolset.name, {}]),
	);
}

function removeDependents(
	removals: Set<string>,
	selected: Set<string>,
	toolsetsByName: Map<string, MemoryAgentToolsetOption>,
) {
	let changed = true;
	while (changed) {
		changed = false;
		for (const name of selected) {
			if (removals.has(name)) continue;
			const requirements = toolsetsByName.get(name)?.requires ?? [];
			if (requirements.some((requirement) => removals.has(requirement))) {
				removals.add(name);
				changed = true;
			}
		}
	}
}

function selectWithRequirements(
	name: string,
	selected: Set<string>,
	toolsetsByName: Map<string, MemoryAgentToolsetOption>,
) {
	const additions = new Set<string>();
	const pending = [name];
	while (pending.length > 0) {
		const next = pending.pop();
		if (next === undefined || additions.has(next)) continue;
		additions.add(next);
		for (const requirement of toolsetsByName.get(next)?.requires ?? []) {
			pending.push(requirement);
		}
	}

	const removals = new Set<string>();
	for (const addition of additions) {
		for (const excluded of toolsetsByName.get(addition)?.excludes ?? []) {
			if (!additions.has(excluded)) removals.add(excluded);
		}
	}
	removeDependents(removals, selected, toolsetsByName);
	for (const removal of removals) selected.delete(removal);
	for (const addition of additions) selected.add(addition);
}

function LoadedCreateMemoryJobForm({
	config,
	memoryGroupId,
	onCreated,
	closeDialog,
}: CreateMemoryJobFormProps & { config: MemoryAgentConfig }) {
	const [submitError, setSubmitError] = useState<string | null>(null);
	const [configuringToolset, setConfiguringToolset] = useState<MemoryAgentToolsetOption | null>(
		null,
	);
	const {
		control,
		formState: { errors, isSubmitting },
		getValues,
		handleSubmit,
		register,
		setValue,
	} = useForm<MemoryJobFormValues>({
		defaultValues: {
			startChapterNum: "",
			endChapterNum: "",
			modelName: config.models[0].name,
			toolsets: defaultToolsets(config),
		},
	});
	const toolsets = useWatch({ control, name: "toolsets" });
	const toolsetsByName = new Map(config.toolsets.map((toolset) => [toolset.name, toolset]));

	function changeToolset(name: string, enabled: boolean) {
		const selected = new Set(Object.keys(toolsets));
		if (enabled) {
			selectWithRequirements(name, selected, toolsetsByName);
		} else {
			const removals = new Set([name]);
			removeDependents(removals, selected, toolsetsByName);
			for (const removal of removals) selected.delete(removal);
		}
		setValue(
			"toolsets",
			Object.fromEntries(
				[...selected].map((toolsetName) => [toolsetName, toolsets[toolsetName] ?? {}]),
			),
			{ shouldDirty: true },
		);
	}

	async function submit(values: MemoryJobFormValues) {
		setSubmitError(null);
		const payload: CreateMemoryJob = {
			memoryGroupId,
			startChapterNum: values.startChapterNum === "" ? null : Number(values.startChapterNum),
			endChapterNum: values.endChapterNum === "" ? null : Number(values.endChapterNum),
			params: {
				modelName: values.modelName,
				toolsets: values.toolsets,
			},
		};

		try {
			const response = await addMemoryJobMemoryAgentJobsPost(payload);
			if (response.status !== 201) {
				setSubmitError(apiErrorMessage(response.data, "Could not create the job."));
				return;
			}
			await onCreated(response.data.memoryJobId);
			closeDialog();
		} catch (error) {
			setSubmitError(requestErrorMessage(error));
		}
	}

	function handleOpenChange(open: boolean) {
		if (!open && !isSubmitting) closeDialog();
	}

	return (
		<>
			<Dialog open onOpenChange={handleOpenChange}>
				<DialogContent
					className="max-h-[calc(100vh-2rem)] overflow-y-auto sm:max-w-2xl"
					showCloseButton={!isSubmitting}
				>
					<DialogHeader>
						<DialogTitle>Create memory-agent job</DialogTitle>
						<DialogDescription>
							Choose the chapter range, model, and toolsets. The job will not start
							until you run it.
						</DialogDescription>
					</DialogHeader>
					<form className="flex flex-col gap-4" onSubmit={handleSubmit(submit)}>
						{submitError !== null && (
							<Alert variant="destructive">
								<AlertDescription>{submitError}</AlertDescription>
							</Alert>
						)}
						<FieldGroup className="gap-3">
							<div className="grid grid-cols-2 gap-2">
								<Field data-invalid={Boolean(errors.startChapterNum)}>
									<FieldLabel htmlFor="memory-job-start-chapter">
										Start chapter
									</FieldLabel>
									<Input
										id="memory-job-start-chapter"
										type="number"
										min={0}
										placeholder="First"
										disabled={isSubmitting}
										{...register("startChapterNum", {
											validate: (value) =>
												value === "" ||
												Number(value) >= 0 ||
												"Must be zero or greater.",
										})}
									/>
									<FieldError errors={[errors.startChapterNum]} />
								</Field>
								<Field data-invalid={Boolean(errors.endChapterNum)}>
									<FieldLabel htmlFor="memory-job-end-chapter">
										End chapter
									</FieldLabel>
									<Input
										id="memory-job-end-chapter"
										type="number"
										min={0}
										placeholder="Last"
										disabled={isSubmitting}
										{...register("endChapterNum", {
											validate: (value) => {
												if (value === "") return true;
												if (Number(value) < 0)
													return "Must be zero or greater.";
												const start = getValues("startChapterNum");
												return (
													start === "" ||
													Number(value) >= Number(start) ||
													"Must not precede the start chapter."
												);
											},
										})}
									/>
									<FieldError errors={[errors.endChapterNum]} />
								</Field>
							</div>
							<Field>
								<FieldLabel htmlFor="memory-job-model">Model</FieldLabel>
								<Controller
									control={control}
									name="modelName"
									render={({ field }) => (
										<Select
											value={field.value}
											disabled={isSubmitting}
											onValueChange={field.onChange}
										>
											<SelectTrigger id="memory-job-model" className="w-full">
												<SelectValue />
											</SelectTrigger>
											<SelectContent>
												{config.models.map((model) => (
													<SelectItem key={model.name} value={model.name}>
														{model.label}
													</SelectItem>
												))}
											</SelectContent>
										</Select>
									)}
								/>
							</Field>
							<div className="grid grid-cols-1 gap-2">
								{config.toolsets.map((toolset) => {
									const id = `memory-job-${toolset.name}-toolset`;
									const selected = Object.hasOwn(toolsets, toolset.name);
									return (
										<div
											className="flex items-start gap-3 rounded-md border border-border p-3"
											key={toolset.name}
										>
											<Checkbox
												id={id}
												checked={selected}
												disabled={isSubmitting}
												onCheckedChange={(checked) =>
													changeToolset(toolset.name, checked === true)
												}
											/>
											<div className="min-w-0 flex-1">
												<FieldLabel htmlFor={id}>
													{toolset.label}
												</FieldLabel>
												<p className="text-xs text-muted-foreground">
													{toolset.description}
												</p>
											</div>
											{toolsetHasConfig(toolset) && (
												<Button
													type="button"
													aria-label={`Configure ${toolset.label}`}
													variant="outline"
													size="sm"
													disabled={!selected || isSubmitting}
													onClick={() => setConfiguringToolset(toolset)}
												>
													<Settings2Icon />
													Configure
												</Button>
											)}
										</div>
									);
								})}
							</div>
							<p className="text-xs text-muted-foreground">
								Selecting a toolset also selects its requirements. Removing a
								requirement removes dependent toolsets.
							</p>
						</FieldGroup>
						<DialogFooter>
							<Button
								type="button"
								variant="outline"
								disabled={isSubmitting}
								onClick={closeDialog}
							>
								Cancel
							</Button>
							<Button type="submit" disabled={isSubmitting}>
								{isSubmitting ? (
									<LoaderCircleIcon className="animate-spin" />
								) : (
									<PlaySquareIcon />
								)}
								{isSubmitting ? "Creating…" : "Create job"}
							</Button>
						</DialogFooter>
					</form>
				</DialogContent>
			</Dialog>
			{configuringToolset !== null && (
				<ToolsetConfigDialog
					key={configuringToolset.name}
					toolset={configuringToolset}
					value={toolsets[configuringToolset.name] ?? {}}
					onClose={() => setConfiguringToolset(null)}
					onSave={(value) => {
						setValue(
							"toolsets",
							{ ...getValues("toolsets"), [configuringToolset.name]: value },
							{ shouldDirty: true },
						);
						setConfiguringToolset(null);
					}}
				/>
			)}
		</>
	);
}

export function CreateMemoryJobForm(props: CreateMemoryJobFormProps) {
	const [config, setConfig] = useState<MemoryAgentConfig | null>(null);
	const [configError, setConfigError] = useState<string | null>(null);

	useEffect(() => {
		const controller = new AbortController();
		void readMemoryAgentConfigMemoryAgentConfigGet({ signal: controller.signal })
			.then((response) => {
				if (controller.signal.aborted) return;
				if (response.status !== 200) {
					setConfigError(
						apiErrorMessage(
							response.data,
							"Could not load memory-agent configuration.",
						),
					);
					return;
				}
				if (response.data.models.length === 0) {
					setConfigError("No memory-agent models are currently available.");
					return;
				}
				setConfig(response.data);
			})
			.catch((error: unknown) => {
				if (!controller.signal.aborted) setConfigError(requestErrorMessage(error));
			});
		return () => controller.abort();
	}, []);

	if (config !== null) return <LoadedCreateMemoryJobForm {...props} config={config} />;

	return (
		<Dialog open onOpenChange={(open) => !open && props.closeDialog()}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>Create memory-agent job</DialogTitle>
					<DialogDescription>Loading available models and toolsets.</DialogDescription>
				</DialogHeader>
				{configError === null ? (
					<div className="flex items-center gap-2 text-muted-foreground">
						<LoaderCircleIcon className="animate-spin" />
						Loading configuration…
					</div>
				) : (
					<Alert variant="destructive">
						<AlertDescription>{configError}</AlertDescription>
					</Alert>
				)}
				<DialogFooter>
					<Button type="button" variant="outline" onClick={props.closeDialog}>
						Close
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
