import { removeMemoryMemoriesMemoryIdDelete } from "@/api/endpoints/default/default";
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
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { AlertCircleIcon } from "lucide-react";
import { useState } from "react";

export function DeleteMemoryDialog({
	memory,
	closeDialog,
	reloadMemoriesAfterDelete,
	reloadAdditionalData,
}: {
	memory: Memory;
	closeDialog: () => void;
	reloadMemoriesAfterDelete: () => void;
	reloadAdditionalData?: () => void;
}) {
	const [submitting, setSubmitting] = useState(false);
	const [submitError, setSubmitError] = useState<string | null>(null);

	function handleOpenChange(nextOpen: boolean) {
		if (!nextOpen && !submitting) closeDialog();
	}

	async function deleteMemory() {
		setSubmitting(true);
		setSubmitError(null);
		try {
			const response = await removeMemoryMemoriesMemoryIdDelete(memory.memoryId);
			if (response.status !== 204) {
				setSubmitError(apiErrorMessage(response.data, "Could not delete the memory."));
				return;
			}
			reloadMemoriesAfterDelete();
			reloadAdditionalData?.();
			closeDialog();
		} catch (error) {
			setSubmitError(requestErrorMessage(error));
		} finally {
			setSubmitting(false);
		}
	}

	return (
		<Dialog open onOpenChange={handleOpenChange}>
			<DialogContent showCloseButton={!submitting}>
				<DialogHeader>
					<DialogTitle>Delete memory?</DialogTitle>
					<DialogDescription>
						This permanently deletes the memory and all of its plugin associations. This
						action cannot be undone.
					</DialogDescription>
				</DialogHeader>
				<p className="line-clamp-4 whitespace-pre-wrap rounded-md border bg-muted/30 p-3 text-sm">
					{memory.memoryContent}
				</p>
				{submitError !== null && (
					<Alert variant="destructive">
						<AlertCircleIcon />
						<AlertTitle>Could not delete the memory</AlertTitle>
						<AlertDescription>{submitError}</AlertDescription>
					</Alert>
				)}
				<DialogFooter>
					<Button variant="outline" disabled={submitting} onClick={closeDialog}>
						Cancel
					</Button>
					<Button variant="destructive" disabled={submitting} onClick={deleteMemory}>
						{submitting ? "Deleting…" : "Delete memory"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
