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
	} = useForm<{
		startChapterNum: string;
		endChapterNum: string;
		modelName: ModelName;
		includeGlossaryTerms: boolean;
		includeGlossaryEvents: boolean;
	}>({
		defaultValues: {
			startChapterNum: "",
			endChapterNum: "",
			modelName: "deepseek:deepseek-v4-flash",
			includeGlossaryTerms: true,
			includeGlossaryEvents: true,
		},
	});

	async function submit(values: {
		startChapterNum: string;
		endChapterNum: string;
		modelName: ModelName;
		includeGlossaryTerms: boolean;
		includeGlossaryEvents: boolean;
	}) {
		setSubmitError(null);
		const toolsets: ToolsetName[] = [];
		if (values.includeGlossaryTerms) toolsets.push("glossary_terms");
		if (values.includeGlossaryEvents) toolsets.push("glossary_events");
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
			<DialogContent showCloseButton={!isSubmitting}>
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
											<SelectItem value="deepseek:deepseek-v4-flash">
												DeepSeek V4 Flash
											</SelectItem>
											<SelectItem value="deepseek:deepseek-v4-pro">
												DeepSeek V4 Pro
											</SelectItem>
										</SelectContent>
									</Select>
								)}
							/>
						</Field>
						<div className="flex items-center gap-2">
							<Controller
								control={control}
								name="includeGlossaryTerms"
								render={({ field }) => (
									<Checkbox
										id="memory-job-glossary-terms-toolset"
										checked={field.value}
										disabled={isSubmitting}
										onCheckedChange={(checked) =>
											field.onChange(checked === true)
										}
									/>
								)}
							/>
							<FieldLabel htmlFor="memory-job-glossary-terms-toolset">
								Glossary terms
							</FieldLabel>
						</div>
						<div className="flex items-center gap-2">
							<Controller
								control={control}
								name="includeGlossaryEvents"
								render={({ field }) => (
									<Checkbox
										id="memory-job-glossary-events-toolset"
										checked={field.value}
										disabled={isSubmitting}
										onCheckedChange={(checked) =>
											field.onChange(checked === true)
										}
									/>
								)}
							/>
							<div>
								<FieldLabel htmlFor="memory-job-glossary-events-toolset">
									Glossary events
								</FieldLabel>
								<p className="text-xs text-muted-foreground">
									Without glossary terms, events can only reference existing
									terms.
								</p>
							</div>
						</div>
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
