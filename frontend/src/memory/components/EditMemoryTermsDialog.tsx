import { replaceGlossaryMemoryTermsMemoryGroupsMemoryGroupIdGlossaryMemoriesMemoryIdTermsPut } from "@/api/endpoints/default/default";
import type { GlossaryTerm, Memory } from "@/api/models";
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
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { AlertCircleIcon } from "lucide-react";
import { useState } from "react";
import { GlossaryTermPicker } from "./GlossaryTermPicker";

export function EditMemoryTermsDialog({
	memoryGroupId,
	memory,
	terms,
	closeDialog,
	reloadMemories,
	reloadTerms,
}: {
	memoryGroupId: string;
	memory: Memory;
	terms: readonly GlossaryTerm[];
	closeDialog: () => void;
	reloadMemories: () => void;
	reloadTerms?: () => void;
}) {
	const [selectedTerms, setSelectedTerms] = useState<readonly GlossaryTerm[]>(terms);
	const [submitting, setSubmitting] = useState(false);
	const [submitError, setSubmitError] = useState<string | null>(null);

	function handleOpenChange(nextOpen: boolean) {
		if (!nextOpen && !submitting) closeDialog();
	}

	function setTermSelected(term: GlossaryTerm, selected: boolean) {
		setSelectedTerms((current) =>
			selected
				? current.some((candidate) => candidate.termId === term.termId)
					? current
					: [...current, term]
				: current.filter((candidate) => candidate.termId !== term.termId),
		);
		setSubmitError(null);
	}

	async function saveTerms() {
		if (selectedTerms.length === 0) return;
		setSubmitting(true);
		setSubmitError(null);
		try {
			const response =
				await replaceGlossaryMemoryTermsMemoryGroupsMemoryGroupIdGlossaryMemoriesMemoryIdTermsPut(
					memoryGroupId,
					memory.memoryId,
					{ termIds: selectedTerms.map((term) => term.termId) },
				);
			if (response.status !== 200) {
				setSubmitError(
					apiErrorMessage(response.data, "Could not change the associated terms."),
				);
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
			<DialogContent
				className="max-h-[calc(100vh-2rem)] overflow-y-auto sm:max-w-xl"
				showCloseButton={!submitting}
			>
				<DialogHeader>
					<DialogTitle>Edit associated terms</DialogTitle>
					<DialogDescription>
						Choose the glossary terms described by this memory.
					</DialogDescription>
				</DialogHeader>
				<Field data-invalid={selectedTerms.length === 0}>
					<FieldLabel>Terms</FieldLabel>
					<GlossaryTermPicker
						memoryGroupId={memoryGroupId}
						selectedTerms={selectedTerms}
						disabled={submitting}
						setTermSelected={setTermSelected}
					/>
					{selectedTerms.length === 0 && (
						<FieldError>Select at least one term.</FieldError>
					)}
				</Field>
				{submitError !== null && (
					<Alert variant="destructive">
						<AlertCircleIcon />
						<AlertTitle>Could not change the associated terms</AlertTitle>
						<AlertDescription>{submitError}</AlertDescription>
					</Alert>
				)}
				<DialogFooter>
					<Button variant="outline" disabled={submitting} onClick={closeDialog}>
						Cancel
					</Button>
					<Button disabled={submitting || selectedTerms.length === 0} onClick={saveTerms}>
						{submitting ? "Saving…" : "Save terms"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
