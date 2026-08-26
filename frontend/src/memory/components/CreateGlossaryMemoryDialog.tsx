import { addGlossaryMemoryMemoryGroupsMemoryGroupIdGlossaryMemoriesPost } from "@/api/endpoints/default/default";
import { MemoryType, Scope, type GlossaryTerm } from "@/api/models";
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
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { useGlossaryMemoryForm } from "@/memory/hooks/useGlossaryMemoryForm";
import { AlertCircleIcon } from "lucide-react";
import { GlossaryTermPicker } from "./GlossaryTermPicker";

function isMemoryType(value: string): value is MemoryType {
	return Object.values(MemoryType).some((candidate) => candidate === value);
}

function isScope(value: string): value is Scope {
	return Object.values(Scope).some((candidate) => candidate === value);
}

export function CreateGlossaryMemoryDialog({
	memoryGroupId,
	chapterId,
	chapterContentId,
	initialTerm,
	closeDialog,
	reloadTerms,
}: {
	memoryGroupId: string;
	chapterId: string;
	chapterContentId: string;
	initialTerm: GlossaryTerm;
	closeDialog: () => void;
	reloadTerms: () => void;
}) {
	const form = useGlossaryMemoryForm([initialTerm]);
	const submitting = form.formStatus.status === "submitting";

	function handleOpenChange(nextOpen: boolean) {
		if (!nextOpen && !submitting) closeDialog();
	}

	async function submit(event: React.SubmitEvent<HTMLFormElement>) {
		event.preventDefault();
		const memoryContent = form.memoryContent.trim();
		if (memoryContent.length === 0 || form.selectedTermIds.length === 0) return;

		form.preSend();
		try {
			const response = await addGlossaryMemoryMemoryGroupsMemoryGroupIdGlossaryMemoriesPost(
				memoryGroupId,
				{
					chapterContentId,
					chapterId,
					memoryContent,
					memoryType: form.memoryType,
					scope: form.scope,
					termIds: form.selectedTermIds,
				},
			);
			if (response.status !== 200) {
				form.onSendError(apiErrorMessage(response.data, "Could not create the memory."));
				return;
			}
			form.onSendSuccess();
			reloadTerms();
			closeDialog();
		} catch (error) {
			form.onSendError(requestErrorMessage(error));
		}
	}

	return (
		<Dialog open onOpenChange={handleOpenChange}>
			<DialogContent
				className="max-h-[calc(100vh-2rem)] overflow-y-auto sm:max-w-xl"
				showCloseButton={!submitting}
			>
				<DialogHeader>
					<DialogTitle>New glossary memory</DialogTitle>
					<DialogDescription>
						Record information observed in the currently open chapter.
					</DialogDescription>
				</DialogHeader>
				<form className="flex flex-col gap-6" onSubmit={submit}>
					{form.formStatus.status === "error" && (
						<Alert variant="destructive">
							<AlertCircleIcon />
							<AlertTitle>Could not create the memory</AlertTitle>
							<AlertDescription>{form.formStatus.message}</AlertDescription>
						</Alert>
					)}
					<FieldGroup>
						<Field>
							<FieldLabel htmlFor="create-glossary-memory-content">
								Content
							</FieldLabel>
							<Textarea
								id="create-glossary-memory-content"
								value={form.memoryContent}
								disabled={submitting}
								rows={4}
								required
								onChange={(event) => form.setMemoryContent(event.target.value)}
							/>
						</Field>
						<div className="grid gap-4 sm:grid-cols-2">
							<Field>
								<FieldLabel htmlFor="create-glossary-memory-type">Type</FieldLabel>
								<Select
									value={form.memoryType}
									disabled={submitting}
									onValueChange={(value) => {
										if (isMemoryType(value)) form.setMemoryType(value);
									}}
								>
									<SelectTrigger
										id="create-glossary-memory-type"
										className="w-full"
									>
										<SelectValue />
									</SelectTrigger>
									<SelectContent>
										<SelectItem value={MemoryType.fact}>Fact</SelectItem>
										<SelectItem value={MemoryType.event}>Event</SelectItem>
										<SelectItem value={MemoryType.def}>Definition</SelectItem>
										<SelectItem value={MemoryType.rel}>Relation</SelectItem>
									</SelectContent>
								</Select>
							</Field>
							<Field>
								<FieldLabel htmlFor="create-glossary-memory-scope">
									Scope
								</FieldLabel>
								<Select
									value={form.scope ?? "auto"}
									disabled={submitting}
									onValueChange={(value) => {
										if (value === "auto") form.setScope(null);
										else if (isScope(value)) form.setScope(value);
									}}
								>
									<SelectTrigger
										id="create-glossary-memory-scope"
										className="w-full"
									>
										<SelectValue />
									</SelectTrigger>
									<SelectContent>
										<SelectItem value="auto">Automatic</SelectItem>
										<SelectItem value={Scope.local}>Current chapter</SelectItem>
										<SelectItem value={Scope.recent}>
											Recent chapters
										</SelectItem>
										<SelectItem value={Scope.persist}>Persistent</SelectItem>
									</SelectContent>
								</Select>
							</Field>
						</div>
						<Field data-invalid={form.selectedTermIds.length === 0}>
							<FieldLabel>Terms</FieldLabel>
							<GlossaryTermPicker
								memoryGroupId={memoryGroupId}
								selectedTerms={form.selectedTerms}
								disabled={submitting}
								setTermSelected={form.setTermSelected}
							/>
							{form.selectedTermIds.length === 0 && (
								<FieldError>Select at least one term.</FieldError>
							)}
						</Field>
					</FieldGroup>
					<DialogFooter>
						<Button
							type="button"
							variant="outline"
							disabled={submitting}
							onClick={() => handleOpenChange(false)}
						>
							Cancel
						</Button>
						<Button
							type="submit"
							disabled={
								submitting ||
								form.memoryContent.trim().length === 0 ||
								form.selectedTermIds.length === 0
							}
						>
							{submitting ? "Creating…" : "Create memory"}
						</Button>
					</DialogFooter>
				</form>
			</DialogContent>
		</Dialog>
	);
}
