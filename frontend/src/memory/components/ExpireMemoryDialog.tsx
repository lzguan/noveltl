import { editMemoryExpirationMemoriesMemoryIdExpirationPatch } from "@/api/endpoints/default/default";
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

export function ExpireMemoryDialog({
	memory,
	chapterId,
	closeDialog,
	reloadMemories,
	reloadTerms,
}: {
	memory: Memory;
	chapterId: string;
	closeDialog: () => void;
	reloadMemories: () => void;
	reloadTerms?: () => void;
}) {
	const [submitting, setSubmitting] = useState(false);
	const [submitError, setSubmitError] = useState<string | null>(null);

	function handleOpenChange(nextOpen: boolean) {
		if (!nextOpen && !submitting) closeDialog();
	}

	async function expireMemory() {
		setSubmitting(true);
		setSubmitError(null);
		try {
			const response = await editMemoryExpirationMemoriesMemoryIdExpirationPatch(
				memory.memoryId,
				{ chapterId },
			);
			if (response.status !== 200) {
				setSubmitError(apiErrorMessage(response.data, "Could not expire the memory."));
				return;
			}
			reloadMemories();
			reloadTerms?.();
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
					<DialogTitle>Expire memory?</DialogTitle>
					<DialogDescription>
						The memory will stop being active at the beginning of the currently open
						chapter. It will remain available in the all-chapters view.
					</DialogDescription>
				</DialogHeader>
				{submitError !== null && (
					<Alert variant="destructive">
						<AlertCircleIcon />
						<AlertTitle>Could not expire the memory</AlertTitle>
						<AlertDescription>{submitError}</AlertDescription>
					</Alert>
				)}
				<DialogFooter>
					<Button variant="outline" disabled={submitting} onClick={closeDialog}>
						Cancel
					</Button>
					<Button disabled={submitting} onClick={expireMemory}>
						{submitting ? "Expiring…" : "Expire memory"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
