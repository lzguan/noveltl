import { addGlossaryMemoryMemoryGroupsMemoryGroupIdGlossaryMemoriesPost } from "@/api/endpoints/default/default";
import { MemoryType, Scope, type GlossaryTerm } from "@/api/models";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { useGlossaryMemoryForm } from "@/memory/hooks/useGlossaryMemoryForm";
import { useGlossaryTerms } from "@/memory/hooks/useGlossaryTerms";
import { AlertCircleIcon, XIcon } from "lucide-react";
import { useEffect } from "react";
import { PageNavigation } from "./PageNavigation";

function isMemoryType(value: string): value is MemoryType {
	return Object.values(MemoryType).some((candidate) => candidate === value);
}

function isScope(value: string): value is Scope {
	return Object.values(Scope).some((candidate) => candidate === value);
}

function GlossaryTermPicker({
	memoryGroupId,
	selectedTerms,
	disabled,
	onTermSelected,
}: {
	memoryGroupId: string;
	selectedTerms: readonly GlossaryTerm[];
	disabled: boolean;
	onTermSelected: (term: GlossaryTerm, selected: boolean) => void;
}) {
	const picker = useGlossaryTerms(memoryGroupId, null);

	useEffect(() => {
		// This picker always searches the complete memory-group glossary.
		picker.setShowAllTerms(true);
		// oxlint-disable-next-line react-hooks/exhaustive-deps
	}, []);

	return (
		<div className="flex flex-col gap-2">
			<div className="flex min-h-9 flex-wrap items-center gap-1.5 rounded-md border border-input px-2 py-1.5">
				{selectedTerms.map((term) => (
					<span
						key={term.termId}
						className="flex items-center gap-1 rounded-sm bg-muted px-1.5 py-0.5 text-xs font-medium"
					>
						{term.term}
						<Button
							type="button"
							variant="ghost"
							size="icon-xs"
							className="-mr-1 size-5"
							aria-label={`Remove ${term.term}`}
							disabled={disabled}
							onClick={() => onTermSelected(term, false)}
						>
							<XIcon />
						</Button>
					</span>
				))}
				<Input
					className="h-7 min-w-36 flex-1 border-0 px-1 shadow-none focus-visible:ring-0"
					aria-label="Search for another term"
					placeholder="Search for another term…"
					value={picker.search}
					disabled={disabled}
					onChange={(event) => picker.setSearch(event.target.value)}
				/>
			</div>

			{picker.terms.status === "idle" || picker.terms.status === "loading" ? (
				<div aria-busy="true" className="flex flex-col gap-1 rounded-md border p-2">
					<Skeleton className="h-7 w-full" />
					<Skeleton className="h-7 w-full" />
				</div>
			) : picker.terms.status === "error" ? (
				<div className="flex items-center justify-between gap-2 text-xs text-destructive">
					<span>{picker.terms.message}</span>
					<Button type="button" variant="outline" size="sm" onClick={picker.reloadTerms}>
						Retry
					</Button>
				</div>
			) : picker.terms.data.items.length === 0 ? (
				<p className="rounded-md border p-2 text-xs text-muted-foreground">
					No matching terms.
				</p>
			) : (
				<div className="rounded-md border">
					<div className="max-h-40 overflow-y-auto p-1">
						{picker.terms.data.items.map((term) => {
							const selected = selectedTerms.some(
								(candidate) => candidate.termId === term.termId,
							);
							return (
								<label
									key={term.termId}
									className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent"
								>
									<Checkbox
										checked={selected}
										disabled={disabled}
										onCheckedChange={(checked) =>
											onTermSelected(term, checked === true)
										}
									/>
									<span className="min-w-0 flex-1 truncate">{term.term}</span>
								</label>
							);
						})}
					</div>
					{!disabled && (
						<PageNavigation
							start={picker.terms.data.start}
							end={picker.terms.data.end}
							total={picker.terms.data.total}
							hasPrevious={picker.terms.data.hasPrevious}
							hasNext={picker.terms.data.hasNext}
							onPrevious={picker.loadPreviousPage}
							onNext={picker.loadNextPage}
						/>
					)}
				</div>
			)}
		</div>
	);
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
								onTermSelected={form.setTermSelected}
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
