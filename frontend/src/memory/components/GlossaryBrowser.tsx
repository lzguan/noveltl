import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { GlossaryTermSummary } from "@/api/models";
import { CreateGlossaryMemoryDialog } from "./CreateGlossaryMemoryDialog";
import { CreateGlossaryTermDialog } from "./CreateGlossaryTermDialog";
import { useGlossaryTerms } from "@/memory/hooks/useGlossaryTerms";
import { PlusIcon, RefreshCwIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { GlossaryTermList } from "./GlossaryTermList";
import { PageNavigation } from "./PageNavigation";

export function GlossaryBrowser({
	memoryGroupId,
	chapterId,
	chapterNum,
	chapterContentId,
}: {
	memoryGroupId: string;
	chapterId: string | null;
	chapterNum: number | null;
	chapterContentId: string | null;
}) {
	const glossary = useGlossaryTerms(memoryGroupId, chapterId);
	const [openTermId, setOpenTermId] = useState<string | null>(null);
	const [createTermOpen, setCreateTermOpen] = useState(false);
	const [memorySeedTerm, setMemorySeedTerm] = useState<GlossaryTermSummary | null>(null);

	useEffect(() => {
		// Mounting this keyed browser establishes a new group/chapter query context.
		// Search, scope, and pagination issue their requests directly from events.
		glossary.loadTerms();
		// oxlint-disable-next-line react-hooks/exhaustive-deps
	}, []);

	const nestedChapterId = glossary.showAllTerms ? null : chapterId;

	function runOuterQuery(runQuery: () => void) {
		setOpenTermId(null);
		runQuery();
	}

	function reloadTerms() {
		setMemorySeedTerm(null);
		runOuterQuery(glossary.reloadTerms);
	}

	return (
		<div className="flex min-h-0 flex-1 flex-col">
			<div className="flex flex-col gap-3 border-b p-2">
				<div className="flex flex-col gap-1">
					<Label htmlFor="glossary-term-search" className="text-xs text-muted-foreground">
						Search terms
					</Label>
					<Input
						id="glossary-term-search"
						value={glossary.search}
						placeholder="Search glossary terms"
						onChange={(event) =>
							runOuterQuery(() => glossary.setSearch(event.target.value))
						}
					/>
				</div>
				<div className="flex items-center gap-2">
					<Switch
						id="glossary-show-all-terms"
						checked={glossary.showAllTerms}
						onCheckedChange={(showAllTerms) =>
							runOuterQuery(() => glossary.setShowAllTerms(showAllTerms))
						}
					/>
					<Label htmlFor="glossary-show-all-terms" className="text-xs">
						Show all terms
					</Label>
					<Button
						variant="ghost"
						size="sm"
						className="ml-auto"
						onClick={() => setCreateTermOpen(true)}
					>
						<PlusIcon /> New term
					</Button>
					<Button
						variant="ghost"
						size="icon-sm"
						aria-label="Refresh glossary terms"
						title="Refresh glossary terms"
						disabled={glossary.terms.status === "loading"}
						onClick={() => runOuterQuery(glossary.reloadTerms)}
					>
						<RefreshCwIcon />
					</Button>
				</div>
			</div>

			{glossary.terms.status === "idle" && chapterId === null && !glossary.showAllTerms ? (
				<Empty>
					<EmptyHeader>
						<EmptyTitle>No chapter open</EmptyTitle>
						<EmptyDescription>
							Open a chapter or select Show all terms to browse the glossary.
						</EmptyDescription>
					</EmptyHeader>
				</Empty>
			) : glossary.terms.status === "error" ? (
				<div className="flex flex-col items-start gap-2 p-3 text-sm text-destructive">
					<p>{glossary.terms.message}</p>
					<Button
						variant="outline"
						size="sm"
						onClick={() => runOuterQuery(glossary.reloadTerms)}
					>
						Retry
					</Button>
				</div>
			) : (
				<>
					<GlossaryTermList
						terms={glossary.terms}
						memoryGroupId={memoryGroupId}
						chapterId={nestedChapterId}
						chapterNum={chapterNum}
						openTermId={openTermId}
						onOpenTermIdChange={setOpenTermId}
						onAddMemory={setMemorySeedTerm}
						memoryCreationDisabled={chapterId === null || chapterContentId === null}
						reloadTerms={reloadTerms}
						reloadTermsAfterDelete={glossary.reloadTermsAfterDelete}
					/>
					{glossary.terms.status === "ready" && glossary.terms.data.items.length > 0 && (
						<PageNavigation
							start={glossary.terms.data.start}
							end={glossary.terms.data.end}
							total={glossary.terms.data.total}
							hasPrevious={glossary.terms.data.hasPrevious}
							hasNext={glossary.terms.data.hasNext}
							onPrevious={() => runOuterQuery(glossary.loadPreviousPage)}
							onNext={() => runOuterQuery(glossary.loadNextPage)}
						/>
					)}
				</>
			)}
			{createTermOpen && (
				<CreateGlossaryTermDialog
					memoryGroupId={memoryGroupId}
					closeDialog={() => setCreateTermOpen(false)}
					reloadTerms={reloadTerms}
				/>
			)}
			{memorySeedTerm !== null && chapterId !== null && chapterContentId !== null && (
				<CreateGlossaryMemoryDialog
					memoryGroupId={memoryGroupId}
					chapterId={chapterId}
					chapterContentId={chapterContentId}
					initialTerm={memorySeedTerm}
					closeDialog={() => setMemorySeedTerm(null)}
					reloadTerms={reloadTerms}
				/>
			)}
		</div>
	);
}
