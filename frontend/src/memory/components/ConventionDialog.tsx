import {
	addConventionMemoryGroupsMemoryGroupIdConventionsPost,
	putConventionMemoryGroupsMemoryGroupIdConventionsConventionIdPut,
} from "@/api/endpoints/default/default";
import { ConventionCategory, type ConventionRead } from "@/api/models";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { CONVENTION_CATEGORY_OPTIONS, isConventionCategory } from "@/memory/conventionCategories";
import { AlertCircleIcon } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";

type ConventionFormValues = {
	category: ConventionCategory;
	title: string;
	rule: string;
	rationale: string;
};

/** Creates a convention, or replaces an existing one's content when `convention` is set. */
export function ConventionDialog({
	memoryGroupId,
	convention,
	closeDialog,
	reloadConventions,
}: {
	memoryGroupId: string;
	convention: ConventionRead | null;
	closeDialog: () => void;
	reloadConventions: () => void;
}) {
	const editing = convention !== null;
	const [submitError, setSubmitError] = useState<string | null>(null);
	const {
		control,
		formState: { errors, isSubmitting },
		handleSubmit,
		register,
	} = useForm<ConventionFormValues>({
		defaultValues: {
			category: convention?.category ?? ConventionCategory.naming,
			title: convention?.title ?? "",
			rule: convention?.rule ?? "",
			rationale: convention?.rationale ?? "",
		},
	});

	function handleOpenChange(nextOpen: boolean) {
		if (!nextOpen && !isSubmitting) closeDialog();
	}

	async function submit(values: ConventionFormValues) {
		setSubmitError(null);
		const body = {
			category: values.category,
			title: values.title.trim(),
			rule: values.rule.trim(),
			rationale: values.rationale.trim() === "" ? null : values.rationale.trim(),
		};
		try {
			const response = editing
				? await putConventionMemoryGroupsMemoryGroupIdConventionsConventionIdPut(
						memoryGroupId,
						convention.conventionId,
						body,
					)
				: await addConventionMemoryGroupsMemoryGroupIdConventionsPost(memoryGroupId, body);
			if (response.status !== (editing ? 200 : 201)) {
				setSubmitError(apiErrorMessage(response.data, "Could not save the convention."));
				return;
			}
			reloadConventions();
			closeDialog();
		} catch (error) {
			setSubmitError(requestErrorMessage(error));
		}
	}

	return (
		<Dialog open onOpenChange={handleOpenChange}>
			<DialogContent showCloseButton={!isSubmitting}>
				<DialogHeader>
					<DialogTitle>{editing ? "Edit convention" : "New convention"}</DialogTitle>
					<DialogDescription>
						Novel-wide guidance for this memory group's translations. Include examples
						in the rule where they help.
					</DialogDescription>
				</DialogHeader>
				<form className="flex flex-col gap-6" onSubmit={handleSubmit(submit)}>
					{submitError !== null && (
						<Alert variant="destructive">
							<AlertCircleIcon />
							<AlertTitle>Could not save the convention</AlertTitle>
							<AlertDescription>{submitError}</AlertDescription>
						</Alert>
					)}
					<Field>
						<FieldLabel htmlFor="convention-category">Category</FieldLabel>
						<Controller
							name="category"
							control={control}
							render={({ field }) => (
								<Select
									value={field.value}
									disabled={isSubmitting}
									onValueChange={(value) => {
										if (isConventionCategory(value)) field.onChange(value);
									}}
								>
									<SelectTrigger id="convention-category" className="w-full">
										<SelectValue />
									</SelectTrigger>
									<SelectContent>
										{CONVENTION_CATEGORY_OPTIONS.map((option) => (
											<SelectItem key={option.value} value={option.value}>
												{option.label}
											</SelectItem>
										))}
									</SelectContent>
								</Select>
							)}
						/>
						<FieldDescription>
							Naming conventions guide term translation. Style conventions are stored
							for chapter translation.
						</FieldDescription>
					</Field>
					<Field data-invalid={Boolean(errors.title)}>
						<FieldLabel htmlFor="convention-title">Title</FieldLabel>
						<Input
							id="convention-title"
							disabled={isSubmitting}
							aria-invalid={Boolean(errors.title)}
							maxLength={200}
							{...register("title", {
								validate: (value) =>
									value.trim().length > 0 || "Title is required.",
							})}
						/>
						<FieldError errors={[errors.title]} />
					</Field>
					<Field data-invalid={Boolean(errors.rule)}>
						<FieldLabel htmlFor="convention-rule">Rule</FieldLabel>
						<Textarea
							id="convention-rule"
							disabled={isSubmitting}
							aria-invalid={Boolean(errors.rule)}
							{...register("rule", {
								validate: (value) => value.trim().length > 0 || "Rule is required.",
							})}
						/>
						<FieldError errors={[errors.rule]} />
					</Field>
					<Field>
						<FieldLabel htmlFor="convention-rationale">Rationale</FieldLabel>
						<Textarea
							id="convention-rationale"
							disabled={isSubmitting}
							placeholder="Optional"
							{...register("rationale")}
						/>
					</Field>
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
							{isSubmitting ? "Saving…" : "Save convention"}
						</Button>
					</DialogFooter>
				</form>
			</DialogContent>
		</Dialog>
	);
}
