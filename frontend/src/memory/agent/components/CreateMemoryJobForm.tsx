import { addMemoryJobMemoryAgentJobsPost } from "@/api/endpoints/default/default";
import type { CreateMemoryJob, ModelName } from "@/api/models";
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
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { LoaderCircleIcon, PlaySquareIcon } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";

const DEFAULT_MODEL: ModelName = "deepseek:deepseek-chat";

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
		includeGlossary: boolean;
	}>({
		defaultValues: { startChapterNum: "", endChapterNum: "", includeGlossary: true },
	});

	async function submit(values: {
		startChapterNum: string;
		endChapterNum: string;
		includeGlossary: boolean;
	}) {
		setSubmitError(null);
		const payload: CreateMemoryJob = {
			memoryGroupId,
			startChapterNum: values.startChapterNum === "" ? null : Number(values.startChapterNum),
			endChapterNum: values.endChapterNum === "" ? null : Number(values.endChapterNum),
			params: {
				modelName: DEFAULT_MODEL,
				plugins: values.includeGlossary ? ["glossary"] : [],
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
						Choose the chapter range and plugins. The job will not start until you run
						it.
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
						<div className="flex items-center gap-2">
							<Controller
								control={control}
								name="includeGlossary"
								render={({ field }) => (
									<Checkbox
										id="memory-job-glossary-plugin"
										checked={field.value}
										disabled={isSubmitting}
										onCheckedChange={(checked) =>
											field.onChange(checked === true)
										}
									/>
								)}
							/>
							<FieldLabel htmlFor="memory-job-glossary-plugin">
								Glossary plugin
							</FieldLabel>
							<span className="ml-auto text-xs text-muted-foreground">
								DeepSeek Chat
							</span>
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
