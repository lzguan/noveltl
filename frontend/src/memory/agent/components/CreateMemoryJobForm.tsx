import { addMemoryJobMemoryAgentJobsPost } from "@/api/endpoints/default/default";
import type { CreateMemoryJob, ModelName, ToolsetName } from "@/api/models";
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
import { LoaderCircleIcon, PlaySquareIcon } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";

type MemoryJobFormValues = {
	startChapterNum: string;
	endChapterNum: string;
	modelName: ModelName;
	includeGlossaryTerms: boolean;
	includeGlossaryDefinitionsRead: boolean;
	includeGlossaryDefinitionsWrite: boolean;
	includeGlossaryRelationsRead: boolean;
	includeGlossaryRelationsWrite: boolean;
	includeGlossaryFactsRead: boolean;
	includeGlossaryFactsWrite: boolean;
	includeGlossaryGenderRead: boolean;
	includeGlossaryGenderWrite: boolean;
	includeGlossaryEventsRead: boolean;
	includeGlossaryEventsWrite: boolean;
	includeGlossaryGenderTransformation: boolean;
	includeGlossaryCultivation: boolean;
	includeGlossarySystem: boolean;
	includeGlossaryArtifacts: boolean;
};

const TOOLSET_OPTIONS = [
	{
		fieldName: "includeGlossaryTerms",
		toolset: "glossary_terms",
		label: "Glossary terms",
		description: "Create and classify new source-language terms.",
	},
	{
		fieldName: "includeGlossaryDefinitionsRead",
		toolset: "glossary_definitions_read",
		label: "Glossary definitions: read",
		description: "Retrieve canonical term meanings.",
	},
	{
		fieldName: "includeGlossaryDefinitionsWrite",
		toolset: "glossary_definitions_write",
		label: "Glossary definitions: write",
		description: "Maintain canonical meanings. Requires definitions: read.",
	},
	{
		fieldName: "includeGlossaryRelationsRead",
		toolset: "glossary_relations_read",
		label: "Glossary relations: read",
		description: "Retrieve categorized relationships.",
	},
	{
		fieldName: "includeGlossaryRelationsWrite",
		toolset: "glossary_relations_write",
		label: "Glossary relations: write",
		description: "Maintain relationships. Requires relations: read.",
	},
	{
		fieldName: "includeGlossaryFactsRead",
		toolset: "glossary_facts_read",
		label: "Glossary facts: read",
		description: "Retrieve selected continuity-critical attributes.",
	},
	{
		fieldName: "includeGlossaryFactsWrite",
		toolset: "glossary_facts_write",
		label: "Glossary facts: write",
		description: "Maintain selected attributes. Requires facts: read.",
	},
	{
		fieldName: "includeGlossaryGenderRead",
		toolset: "glossary_gender_read",
		label: "Glossary gender: read",
		description: "Retrieve explicitly established gender-related state.",
	},
	{
		fieldName: "includeGlossaryGenderWrite",
		toolset: "glossary_gender_write",
		label: "Glossary gender: write",
		description: "Maintain gender-related state. Requires gender: read.",
	},
	{
		fieldName: "includeGlossaryEventsRead",
		toolset: "glossary_events_read",
		label: "Glossary events: read",
		description: "Retrieve consequential occurrences.",
	},
	{
		fieldName: "includeGlossaryEventsWrite",
		toolset: "glossary_events_write",
		label: "Glossary events: write",
		description: "Maintain consequential occurrences. Requires events: read.",
	},
	{
		fieldName: "includeGlossaryGenderTransformation",
		toolset: "glossary_gender_transformation",
		label: "Gender transformation guidance",
		description:
			"Distinguish lasting changes, reveals, disguises, bodies, and avatars. Requires gender and relation read/write tools.",
	},
	{
		fieldName: "includeGlossaryCultivation",
		toolset: "glossary_cultivation",
		label: "Cultivation guidance",
		description: "Track completed cultivation levels and reject temporary boosts. Requires fact read/write tools.",
	},
	{
		fieldName: "includeGlossarySystem",
		toolset: "glossary_system",
		label: "System guidance",
		description: "Track durable system mechanics and state sparingly. Requires fact read/write tools.",
	},
	{
		fieldName: "includeGlossaryArtifacts",
		toolset: "glossary_artifacts",
		label: "Artifact guidance",
		description: "Track recurring fantastical objects and lasting changes. Requires definition read/write tools.",
	},
] as const;

export function CreateMemoryJobForm({
	memoryGroupId,
	onCreated,
	closeDialog,
}: {
	memoryGroupId: string;
	onCreated: (memoryJobId: string) => Promise<void>;
	closeDialog: () => void;
}) {
	const [submitError, setSubmitError] = useState<string | null>(null);
	const {
		control,
		formState: { errors, isSubmitting },
		getValues,
		handleSubmit,
		register,
		reset,
	} = useForm<MemoryJobFormValues>({
		defaultValues: {
			startChapterNum: "",
			endChapterNum: "",
			modelName: "deepseek:deepseek-v4-flash-none",
			includeGlossaryTerms: true,
			includeGlossaryDefinitionsRead: true,
			includeGlossaryDefinitionsWrite: true,
			includeGlossaryRelationsRead: true,
			includeGlossaryRelationsWrite: true,
			includeGlossaryFactsRead: true,
			includeGlossaryFactsWrite: true,
			includeGlossaryGenderRead: true,
			includeGlossaryGenderWrite: true,
			includeGlossaryEventsRead: true,
			includeGlossaryEventsWrite: true,
			includeGlossaryGenderTransformation: false,
			includeGlossaryCultivation: false,
			includeGlossarySystem: false,
			includeGlossaryArtifacts: false,
		},
	});

	async function submit(values: MemoryJobFormValues) {
		setSubmitError(null);
		const toolsets: ToolsetName[] = [];
		for (const option of TOOLSET_OPTIONS) {
			if (values[option.fieldName]) toolsets.push(option.toolset);
		}
		const payload: CreateMemoryJob = {
			memoryGroupId,
			startChapterNum: values.startChapterNum === "" ? null : Number(values.startChapterNum),
			endChapterNum: values.endChapterNum === "" ? null : Number(values.endChapterNum),
			params: {
				modelName: values.modelName,
				toolsets,
			},
		};

		try {
			const response = await addMemoryJobMemoryAgentJobsPost(payload);
			if (response.status !== 201) {
				setSubmitError(apiErrorMessage(response.data, "Could not create the job."));
				return;
			}
			reset();
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
		<Dialog open onOpenChange={handleOpenChange}>
			<DialogContent
				className="max-h-[calc(100vh-2rem)] overflow-y-auto"
				showCloseButton={!isSubmitting}
			>
				<DialogHeader>
					<DialogTitle>Create memory-agent job</DialogTitle>
					<DialogDescription>
						Choose the chapter range, model, and toolsets. The job will not start until
						you run it.
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
											<SelectItem value="deepseek:deepseek-v4-flash-none">
												DeepSeek V4 Flash (None)
											</SelectItem>
											<SelectItem value="deepseek:deepseek-v4-flash-low">
												DeepSeek V4 Flash (Low)
											</SelectItem>
										</SelectContent>
									</Select>
								)}
							/>
						</Field>
						<div className="flex flex-col gap-3">
							{TOOLSET_OPTIONS.map((option) => {
								const id = `memory-job-${option.toolset}-toolset`;
								return (
									<div className="flex items-start gap-2" key={option.toolset}>
										<Controller
											control={control}
											name={option.fieldName}
											render={({ field }) => (
												<Checkbox
													id={id}
													checked={field.value}
													disabled={isSubmitting}
													onCheckedChange={(checked) =>
														field.onChange(checked === true)
													}
												/>
											)}
										/>
										<div>
											<FieldLabel htmlFor={id}>{option.label}</FieldLabel>
											<p className="text-xs text-muted-foreground">
												{option.description}
											</p>
										</div>
									</div>
								);
							})}
						</div>
						<p className="text-xs text-muted-foreground">
							Memory toolsets can only write for existing terms when glossary term
							creation is disabled.
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
	);
}
