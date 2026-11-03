import { removeConventionMemoryGroupsMemoryGroupIdConventionsConventionIdDelete } from "@/api/endpoints/default/default";
import type { ConventionRead } from "@/api/models";
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

export function DeleteConventionDialog({
	memoryGroupId,
	convention,
	closeDialog,
	reloadConventionsAfterDelete,
}: {
	memoryGroupId: string;
	convention: ConventionRead;
	closeDialog: () => void;
	reloadConventionsAfterDelete: () => void;
}) {
	const [submitting, setSubmitting] = useState(false);
	const [submitError, setSubmitError] = useState<string | null>(null);

	function handleOpenChange(nextOpen: boolean) {
		if (!nextOpen && !submitting) closeDialog();
	}

	async function deleteConvention() {
		setSubmitting(true);
		setSubmitError(null);
		try {
			const response =
				await removeConventionMemoryGroupsMemoryGroupIdConventionsConventionIdDelete(
					memoryGroupId,
					convention.conventionId,
				);
			if (response.status !== 204) {
				setSubmitError(apiErrorMessage(response.data, "Could not delete the convention."));
				return;
			}
			reloadConventionsAfterDelete();
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
					<DialogTitle>Delete convention?</DialogTitle>
					<DialogDescription>
						This permanently deletes the convention. This action cannot be undone.
					</DialogDescription>
				</DialogHeader>
				<p className="line-clamp-4 whitespace-pre-wrap rounded-md border bg-muted/30 p-3 text-sm">
					{convention.title}
				</p>
				{submitError !== null && (
					<Alert variant="destructive">
						<AlertCircleIcon />
						<AlertTitle>Could not delete the convention</AlertTitle>
						<AlertDescription>{submitError}</AlertDescription>
					</Alert>
				)}
				<DialogFooter>
					<Button variant="outline" disabled={submitting} onClick={closeDialog}>
						Cancel
					</Button>
					<Button variant="destructive" disabled={submitting} onClick={deleteConvention}>
						{submitting ? "Deleting…" : "Delete convention"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
