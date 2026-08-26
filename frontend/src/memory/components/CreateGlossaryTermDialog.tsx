import { addGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsPost } from "@/api/endpoints/default/default";
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
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { AlertCircleIcon } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

export function CreateGlossaryTermDialog({
	memoryGroupId,
	closeDialog,
	reloadTerms,
}: {
	memoryGroupId: string;
	closeDialog: () => void;
	reloadTerms: () => void;
}) {
	const [submitError, setSubmitError] = useState<string | null>(null);
	const {
		formState: { errors, isSubmitting },
		handleSubmit,
		register,
	} = useForm<{ term: string }>({ defaultValues: { term: "" } });

	function handleOpenChange(nextOpen: boolean) {
		if (!nextOpen && !isSubmitting) closeDialog();
	}

	async function submit(values: { term: string }) {
		setSubmitError(null);
		try {
			const response = await addGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsPost(
				memoryGroupId,
				{ term: values.term.trim() },
			);
			if (response.status !== 200) {
				setSubmitError(apiErrorMessage(response.data, "Could not create the term."));
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
					<DialogTitle>New glossary term</DialogTitle>
					<DialogDescription>
						Enter the term exactly as it appears in the novel’s source text.
					</DialogDescription>
				</DialogHeader>
				<form className="flex flex-col gap-6" onSubmit={handleSubmit(submit)}>
					{submitError !== null && (
						<Alert variant="destructive">
							<AlertCircleIcon />
							<AlertTitle>Could not create the term</AlertTitle>
							<AlertDescription>{submitError}</AlertDescription>
						</Alert>
					)}
					<Field data-invalid={Boolean(errors.term)}>
						<FieldLabel htmlFor="create-glossary-term">Term</FieldLabel>
						<Input
							id="create-glossary-term"
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
					<DialogFooter>
						<Button
							type="button"
							variant="outline"
							disabled={isSubmitting}
							onClick={() => handleOpenChange(false)}
						>
							Cancel
						</Button>
						<Button type="submit" disabled={isSubmitting}>
							{isSubmitting ? "Creating…" : "Create term"}
						</Button>
					</DialogFooter>
				</form>
			</DialogContent>
		</Dialog>
	);
}
