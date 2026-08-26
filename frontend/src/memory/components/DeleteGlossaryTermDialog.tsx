import { removeGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdDelete } from "@/api/endpoints/default/default";
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
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { AlertCircleIcon } from "lucide-react";
import { useState } from "react";

export function DeleteGlossaryTermDialog({
	memoryGroupId,
	term,
	closeDialog,
	reloadTermsAfterDelete,
}: {
	memoryGroupId: string;
	term: GlossaryTerm;
	closeDialog: () => void;
	reloadTermsAfterDelete: () => void;
}) {
	const [submitting, setSubmitting] = useState(false);
	const [submitError, setSubmitError] = useState<string | null>(null);

	function handleOpenChange(nextOpen: boolean) {
		if (!nextOpen && !submitting) closeDialog();
	}

	async function deleteTerm() {
		setSubmitting(true);
		setSubmitError(null);
		try {
			const response =
				await removeGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdDelete(
					memoryGroupId,
					term.termId,
				);
			if (response.status !== 204) {
				setSubmitError(apiErrorMessage(response.data, "Could not delete the term."));
				return;
			}
			reloadTermsAfterDelete();
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
					<DialogTitle>Delete glossary term?</DialogTitle>
					<DialogDescription>
						This permanently deletes “{term.term}” and removes its memory associations.
						The associated memories themselves will not be deleted.
					</DialogDescription>
				</DialogHeader>
				{submitError !== null && (
					<Alert variant="destructive">
						<AlertCircleIcon />
						<AlertTitle>Could not delete the term</AlertTitle>
						<AlertDescription>{submitError}</AlertDescription>
					</Alert>
				)}
				<DialogFooter>
					<Button variant="outline" disabled={submitting} onClick={closeDialog}>
						Cancel
					</Button>
					<Button variant="destructive" disabled={submitting} onClick={deleteTerm}>
						{submitting ? "Deleting…" : "Delete term"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
