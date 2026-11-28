import { useState } from "react";
import { AlertCircleIcon } from "lucide-react";

import { deletePublishingTargetPublishingTargetsTargetIdDelete } from "@/api/endpoints/publishing/publishing";
import type { PublishingTargetRead } from "@/api/models";
import { Alert, AlertDescription } from "@/components/ui/alert";
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

export function DeletePublishingTargetDialog({
	target,
	onDeleted,
	onClose,
}: {
	target: PublishingTargetRead;
	onDeleted: (targetId: string) => void;
	onClose: () => void;
}) {
	const [deleting, setDeleting] = useState(false);
	const [error, setError] = useState<string | null>(null);

	async function handleDelete() {
		if (deleting) return;
		setDeleting(true);
		setError(null);
		try {
			const resp = await deletePublishingTargetPublishingTargetsTargetIdDelete(
				target.targetId,
			);
			if (resp.status !== 200) {
				setError(apiErrorMessage(resp.data, "Could not delete publishing target."));
				return;
			}
			onDeleted(target.targetId);
			onClose();
		} catch (err: unknown) {
			setError(requestErrorMessage(err));
		} finally {
			setDeleting(false);
		}
	}

	return (
		<Dialog
			open
			onOpenChange={(open) => {
				if (!open && !deleting) onClose();
			}}
		>
			<DialogContent className="sm:max-w-md" showCloseButton={!deleting}>
				<DialogHeader>
					<DialogTitle>Delete publishing target</DialogTitle>
					<DialogDescription>
						Remove <span className="font-medium text-foreground">{target.name}</span>{" "}
						from Studio? This removes the saved connection and API key from Studio, but
						does not delete novels already published on the Reader.
					</DialogDescription>
				</DialogHeader>

				{error !== null && (
					<Alert variant="destructive">
						<AlertCircleIcon />
						<AlertDescription>{error}</AlertDescription>
					</Alert>
				)}

				<DialogFooter>
					<Button type="button" variant="outline" disabled={deleting} onClick={onClose}>
						Cancel
					</Button>
					<Button
						type="button"
						variant="destructive"
						disabled={deleting}
						onClick={() => void handleDelete()}
					>
						{deleting ? "Deleting..." : "Delete target"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
