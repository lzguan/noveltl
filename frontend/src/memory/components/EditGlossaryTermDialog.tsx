import { editGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdPatch } from "@/api/endpoints/default/default";
import type { GlossaryTerm } from "@/api/models";
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
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { isTermKind, TERM_KIND_OPTIONS, UNCATEGORIZED_TERM_KIND } from "@/memory/termKinds";
import { AlertCircleIcon } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";

export function EditGlossaryTermDialog({
	memoryGroupId,
	term,
	closeDialog,
	reloadTerms,
}: {
	memoryGroupId: string;
	term: GlossaryTerm;
	closeDialog: () => void;
	reloadTerms: () => void;
}) {
	const [submitError, setSubmitError] = useState<string | null>(null);
	const {
		control,
		formState: { errors, isSubmitting },
		handleSubmit,
		register,
	} = useForm<{ term: string; termKind: string }>({
		defaultValues: {
			term: term.term,
			termKind: term.termKind ?? UNCATEGORIZED_TERM_KIND,
		},
	});

	function handleOpenChange(nextOpen: boolean) {
		if (!nextOpen && !isSubmitting) closeDialog();
	}

	async function submit(values: { term: string; termKind: string }) {
		setSubmitError(null);
		try {
			const response =
				await editGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdPatch(
					memoryGroupId,
					term.termId,
					{
						term: values.term.trim(),
						termKind: isTermKind(values.termKind) ? values.termKind : null,
					},
				);
			if (response.status !== 200) {
				setSubmitError(apiErrorMessage(response.data, "Could not rename the term."));
				return;
			}
			reloadTerms();
			closeDialog();
		} catch (error) {
			setSubmitError(requestErrorMessage(error));
		}
	}

	return (
		<Dialog open onOpenChange={handleOpenChange}>
			<DialogContent showCloseButton={!isSubmitting}>
				<DialogHeader>
					<DialogTitle>Rename glossary term</DialogTitle>
					<DialogDescription>
						Change the source-language text used for this term.
					</DialogDescription>
				</DialogHeader>
				<form className="flex flex-col gap-6" onSubmit={handleSubmit(submit)}>
					{submitError !== null && (
						<Alert variant="destructive">
							<AlertCircleIcon />
							<AlertTitle>Could not rename the term</AlertTitle>
							<AlertDescription>{submitError}</AlertDescription>
						</Alert>
					)}
					<Field data-invalid={Boolean(errors.term)}>
						<FieldLabel htmlFor="edit-glossary-term">Term</FieldLabel>
						<Input
							id="edit-glossary-term"
							disabled={isSubmitting}
							aria-invalid={Boolean(errors.term)}
							maxLength={100}
							{...register("term", {
								required: "Term is required.",
								validate: (value) => value.trim().length > 0 || "Term is required.",
							})}
						/>
						<FieldError errors={[errors.term]} />
					</Field>
					<Field>
						<FieldLabel htmlFor="edit-glossary-term-kind">Kind</FieldLabel>
						<Controller
							name="termKind"
							control={control}
							render={({ field }) => (
								<Select
									value={field.value}
									disabled={isSubmitting}
									onValueChange={field.onChange}
								>
									<SelectTrigger id="edit-glossary-term-kind" className="w-full">
										<SelectValue />
									</SelectTrigger>
									<SelectContent>
										<SelectItem value={UNCATEGORIZED_TERM_KIND}>
											Uncategorized
										</SelectItem>
										{TERM_KIND_OPTIONS.map((option) => (
											<SelectItem key={option.value} value={option.value}>
												{option.label}
											</SelectItem>
										))}
									</SelectContent>
								</Select>
							)}
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
							{isSubmitting ? "Saving…" : "Save term"}
						</Button>
					</DialogFooter>
				</form>
			</DialogContent>
		</Dialog>
	);
}
