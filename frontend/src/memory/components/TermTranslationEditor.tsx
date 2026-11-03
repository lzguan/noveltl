import {
	editTermTranslationReviewStatusMemoryGroupsMemoryGroupIdTranslationsTermIdReviewStatusPatch,
	putTermTranslationMemoryGroupsMemoryGroupIdTranslationsTermIdPut,
	removeTermTranslationMemoryGroupsMemoryGroupIdTranslationsTermIdDelete,
} from "@/api/endpoints/default/default";
import type { TermTranslationRead } from "@/api/models";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { CheckIcon, PencilIcon, Trash2Icon, XIcon } from "lucide-react";
import { useId, useState, type SubmitEvent } from "react";

export function TermTranslationEditor({
	memoryGroupId,
	term,
	translation,
	onSaved,
	onDeleted,
	showReviewActions = false,
}: {
	memoryGroupId: string;
	term: { termId: string; term: string };
	translation: TermTranslationRead | null;
	onSaved: (translation: TermTranslationRead) => void;
	onDeleted?: (termId: string) => void;
	showReviewActions?: boolean;
}) {
	const inputId = useId();
	const [editing, setEditing] = useState(false);
	const [draft, setDraft] = useState("");
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);

	function edit() {
		setDraft(translation?.translation ?? "");
		setError(null);
		setEditing(true);
	}

	async function save(event: SubmitEvent<HTMLFormElement>) {
		event.preventDefault();
		if (!draft.trim()) {
			setError("Translation is required.");
			return;
		}
		setSaving(true);
		setError(null);
		try {
			const response = await putTermTranslationMemoryGroupsMemoryGroupIdTranslationsTermIdPut(
				memoryGroupId,
				term.termId,
				{ translation: draft.trim() },
			);
			if (response.status !== 200) {
				setError(apiErrorMessage(response.data, "Could not save the translation."));
				return;
			}
			onSaved(response.data);
			setEditing(false);
		} catch (error) {
			setError(requestErrorMessage(error));
		} finally {
			setSaving(false);
		}
	}

	async function review(reviewStatus: "approved" | "rejected") {
		setSaving(true);
		setError(null);
		try {
			const response =
				await editTermTranslationReviewStatusMemoryGroupsMemoryGroupIdTranslationsTermIdReviewStatusPatch(
					memoryGroupId,
					term.termId,
					{ reviewStatus },
				);
			if (response.status !== 200) {
				setError(
					apiErrorMessage(
						response.data,
						"Could not update the translation's review status.",
					),
				);
				return;
			}
			onSaved(response.data);
		} catch (error) {
			setError(requestErrorMessage(error));
		} finally {
			setSaving(false);
		}
	}

	async function remove() {
		setSaving(true);
		setError(null);
		try {
			const response =
				await removeTermTranslationMemoryGroupsMemoryGroupIdTranslationsTermIdDelete(
					memoryGroupId,
					term.termId,
				);
			if (response.status !== 204) {
				setError(apiErrorMessage(response.data, "Could not delete the translation."));
				return;
			}
			onDeleted?.(term.termId);
		} catch (error) {
			setError(requestErrorMessage(error));
		} finally {
			setSaving(false);
		}
	}

	return (
		<div className="min-w-0 space-y-2">
			<div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
				<span>Translation</span>
				{translation !== null && (
					<Badge variant="outline">{translation.reviewStatus}</Badge>
				)}
				{translation?.creatorType === "user" && <span>Edited by user</span>}
			</div>
			{editing ? (
				<form onSubmit={save} className="space-y-2">
					<Field>
						<FieldLabel htmlFor={inputId} className="sr-only">
							Translation for {term.term}
						</FieldLabel>
						<Input
							id={inputId}
							value={draft}
							disabled={saving}
							aria-invalid={error !== null}
							onChange={(event) => setDraft(event.target.value)}
							autoFocus
						/>
					</Field>
					{error !== null && (
						<p role="alert" className="text-xs text-destructive">
							{error}
						</p>
					)}
					<div className="flex flex-wrap justify-end gap-2">
						<Button
							type="button"
							size="sm"
							variant="outline"
							disabled={saving}
							onClick={() => setEditing(false)}
						>
							Cancel
						</Button>
						<Button type="submit" size="sm" disabled={saving}>
							{saving ? "Saving…" : "Save translation"}
						</Button>
					</div>
				</form>
			) : (
				<div className="flex items-start gap-2">
					<p className="min-w-0 flex-1 wrap-break-word text-sm">
						{translation?.translation ?? "Not translated"}
					</p>
					<Button
						type="button"
						variant="ghost"
						size="icon-sm"
						onClick={edit}
						disabled={saving}
						aria-label={`${translation === null ? "Add" : "Edit"} translation for ${term.term}`}
					>
						<PencilIcon />
					</Button>
					{showReviewActions && translation !== null && (
						<>
							<Button
								type="button"
								variant="ghost"
								size="icon-sm"
								disabled={saving || translation.reviewStatus === "approved"}
								onClick={() => review("approved")}
								aria-label={`Approve translation for ${term.term}`}
								title="Approve translation"
							>
								<CheckIcon />
							</Button>
							<Button
								type="button"
								variant="ghost"
								size="icon-sm"
								disabled={saving || translation.reviewStatus === "rejected"}
								onClick={() => review("rejected")}
								aria-label={`Reject translation for ${term.term}`}
								title="Reject translation"
							>
								<XIcon />
							</Button>
							{onDeleted !== undefined && (
								<Button
									type="button"
									variant="ghost"
									size="icon-sm"
									disabled={saving}
									onClick={remove}
									aria-label={`Delete translation for ${term.term}`}
									title="Delete translation"
								>
									<Trash2Icon />
								</Button>
							)}
						</>
					)}
				</div>
			)}
			{!editing && error !== null && (
				<p role="alert" className="text-xs text-destructive">
					{error}
				</p>
			)}
		</div>
	);
}
