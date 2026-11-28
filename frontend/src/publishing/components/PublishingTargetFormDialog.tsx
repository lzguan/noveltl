import { useState, type SubmitEvent } from "react";
import { AlertCircleIcon } from "lucide-react";

import {
	createPublishingTargetPublishingTargetsPost,
	updatePublishingTargetPublishingTargetsTargetIdPatch,
} from "@/api/endpoints/publishing/publishing";
import type { PublishingTargetRead, UpdatePublishingTarget } from "@/api/models";
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
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";

function usePublishingTargetForm(initial?: { name: string; apiBaseUrl: string }) {
	const [name, setName] = useState(initial?.name ?? "");
	const [apiBaseUrl, setApiBaseUrl] = useState(initial?.apiBaseUrl ?? "");
	const [apiKey, setApiKey] = useState("");
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);

	function startSubmit() {
		setSubmitting(true);
		setError(null);
	}

	function submitSuccess() {
		setSubmitting(false);
		setError(null);
	}

	function submitFailure(message: string) {
		setSubmitting(false);
		setError(message);
	}

	return {
		name,
		setName,
		apiBaseUrl,
		setApiBaseUrl,
		apiKey,
		setApiKey,
		submitting,
		error,
		startSubmit,
		submitSuccess,
		submitFailure,
	};
}

type PublishingTargetFormDialogProps =
	| {
			mode: "create";
			onSaved: (target: PublishingTargetRead) => void;
			onClose: () => void;
	  }
	| {
			mode: "edit";
			target: PublishingTargetRead;
			onSaved: (target: PublishingTargetRead) => void;
			onClose: () => void;
	  };

export function PublishingTargetFormDialog(props: PublishingTargetFormDialogProps) {
	const isEdit = props.mode === "edit";
	const form = usePublishingTargetForm(
		isEdit
			? {
					name: props.target.name,
					apiBaseUrl: props.target.apiBaseUrl,
				}
			: undefined,
	);

	async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
		event.preventDefault();
		if (form.submitting) return;

		const trimmedName = form.name.trim();
		const trimmedUrl = form.apiBaseUrl.trim();
		const trimmedKey = form.apiKey.trim();

		if (!trimmedName) {
			form.submitFailure("Target name is required.");
			return;
		}
		if (!trimmedUrl) {
			form.submitFailure("API base URL is required.");
			return;
		}
		if (!isEdit && !trimmedKey) {
			form.submitFailure("API key is required.");
			return;
		}

		form.startSubmit();
		try {
			if (props.mode === "create") {
				const resp = await createPublishingTargetPublishingTargetsPost({
					name: trimmedName,
					apiBaseUrl: trimmedUrl,
					apiKey: trimmedKey,
				});
				if (resp.status !== 201) {
					form.submitFailure(
						apiErrorMessage(resp.data, "Could not verify and save publishing target."),
					);
					return;
				}
				form.submitSuccess();
				props.onSaved(resp.data);
				props.onClose();
				return;
			}

			const payload: UpdatePublishingTarget = {
				name: trimmedName,
				apiBaseUrl: trimmedUrl,
				...(trimmedKey ? { apiKey: trimmedKey } : {}),
			};
			const resp = await updatePublishingTargetPublishingTargetsTargetIdPatch(
				props.target.targetId,
				payload,
			);
			if (resp.status !== 200) {
				form.submitFailure(
					apiErrorMessage(resp.data, "Could not update publishing target."),
				);
				return;
			}
			form.submitSuccess();
			props.onSaved(resp.data);
			props.onClose();
		} catch (err: unknown) {
			form.submitFailure(requestErrorMessage(err));
		}
	}

	return (
		<Dialog
			open
			onOpenChange={(open) => {
				if (!open && !form.submitting) props.onClose();
			}}
		>
			<DialogContent className="sm:max-w-lg" showCloseButton={!form.submitting}>
				<DialogHeader>
					<DialogTitle>
						{isEdit ? "Edit publishing target" : "Add publishing target"}
					</DialogTitle>
					<DialogDescription>
						{isEdit
							? "Update the Reader endpoint details or rotate the stored API key. Changes are tested against the Reader before saving."
							: "Enter a Reader instance URL and publish API key. Studio will test the connection before saving."}
					</DialogDescription>
				</DialogHeader>

				<form className="flex flex-col gap-5" onSubmit={(e) => void handleSubmit(e)}>
					{form.error !== null && (
						<Alert variant="destructive">
							<AlertCircleIcon />
							<AlertDescription>{form.error}</AlertDescription>
						</Alert>
					)}

					<FieldGroup className="gap-4">
						<Field>
							<FieldLabel htmlFor="publishing-target-name">Name</FieldLabel>
							<Input
								id="publishing-target-name"
								placeholder="Production Reader"
								value={form.name}
								disabled={form.submitting}
								onChange={(e) => form.setName(e.target.value)}
								required
							/>
						</Field>

						<Field>
							<FieldLabel htmlFor="publishing-target-url">API Base URL</FieldLabel>
							<Input
								id="publishing-target-url"
								type="url"
								placeholder="https://reader.example.com/api"
								value={form.apiBaseUrl}
								disabled={form.submitting}
								onChange={(e) => form.setApiBaseUrl(e.target.value)}
								required
							/>
							<FieldDescription>
								The Reader API base URL used by Studio to push chapters.
							</FieldDescription>
						</Field>

						<Field>
							<FieldLabel htmlFor="publishing-target-key">
								{isEdit ? "New API Key (optional)" : "API Key"}
							</FieldLabel>
							<Input
								id="publishing-target-key"
								type="password"
								autoComplete="new-password"
								placeholder={
									isEdit
										? "Leave blank to keep existing key"
										: "Paste Reader publish API key"
								}
								value={form.apiKey}
								disabled={form.submitting}
								onChange={(e) => form.setApiKey(e.target.value)}
								required={!isEdit}
							/>
							{isEdit && (
								<FieldDescription>
									Current key starts with{" "}
									<code className="font-mono text-xs">
										{props.target.keyPrefix}…
									</code>
									. Leave blank to keep the existing key.
								</FieldDescription>
							)}
						</Field>
					</FieldGroup>

					<DialogFooter>
						<Button
							type="button"
							variant="outline"
							disabled={form.submitting}
							onClick={props.onClose}
						>
							Cancel
						</Button>
						<Button type="submit" disabled={form.submitting}>
							{isEdit
								? form.submitting
									? "Saving..."
									: "Save changes"
								: form.submitting
									? "Testing & saving..."
									: "Test & save"}
						</Button>
					</DialogFooter>
				</form>
			</DialogContent>
		</Dialog>
	);
}
