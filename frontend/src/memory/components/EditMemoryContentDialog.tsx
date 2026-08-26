import { editMemoryContentMemoriesMemoryIdContentPatch } from "@/api/endpoints/default/default";
import type { Memory } from "@/api/models";
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
import { Textarea } from "@/components/ui/textarea";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { AlertCircleIcon } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

export function EditMemoryContentDialog({
	memory,
	closeDialog,
	reloadMemories,
}: {
	memory: Memory;
	closeDialog: () => void;
	reloadMemories: () => void;
}) {
	const [submitError, setSubmitError] = useState<string | null>(null);
	const {
		formState: { errors, isSubmitting },
		handleSubmit,
		register,
	} = useForm<{ memoryContent: string }>({
		defaultValues: { memoryContent: memory.memoryContent },
	});

	function handleOpenChange(nextOpen: boolean) {
		if (!nextOpen && !isSubmitting) closeDialog();
	}

	async function submit(values: { memoryContent: string }) {
		setSubmitError(null);
		try {
			const response = await editMemoryContentMemoriesMemoryIdContentPatch(memory.memoryId, {
				memoryContent: values.memoryContent.trim(),
			});
			if (response.status !== 200) {
				setSubmitError(apiErrorMessage(response.data, "Could not edit the memory."));
				return;
			}
			reloadMemories();
			closeDialog();
		} catch (error) {
			setSubmitError(requestErrorMessage(error));
		}
	}

	return (
		<Dialog open onOpenChange={handleOpenChange}>
			<DialogContent showCloseButton={!isSubmitting}>
				<DialogHeader>
					<DialogTitle>Edit memory content</DialogTitle>
					<DialogDescription>
						Change the contextual information in this memory.
					</DialogDescription>
				</DialogHeader>
				<form className="flex flex-col gap-6" onSubmit={handleSubmit(submit)}>
					{submitError !== null && (
						<Alert variant="destructive">
							<AlertCircleIcon />
							<AlertTitle>Could not edit the memory</AlertTitle>
							<AlertDescription>{submitError}</AlertDescription>
						</Alert>
					)}
					<Field data-invalid={Boolean(errors.memoryContent)}>
						<FieldLabel htmlFor="edit-memory-content">Content</FieldLabel>
						<Textarea
							id="edit-memory-content"
							disabled={isSubmitting}
							aria-invalid={Boolean(errors.memoryContent)}
							rows={5}
							{...register("memoryContent", {
								required: "Content is required.",
								validate: (value) =>
									value.trim().length > 0 || "Content is required.",
							})}
						/>
						<FieldError errors={[errors.memoryContent]} />
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
							{isSubmitting ? "Saving…" : "Save content"}
						</Button>
					</DialogFooter>
				</form>
			</DialogContent>
		</Dialog>
	);
}
