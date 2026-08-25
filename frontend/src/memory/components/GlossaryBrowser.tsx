import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useGlossaryTerms } from "@/memory/hooks/useGlossaryTerms";
import { RefreshCwIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { GlossaryTermList } from "./GlossaryTermList";
import { PageNavigation } from "./PageNavigation";

export function GlossaryBrowser({
	memoryGroupId,
	chapterId,
}: {
	memoryGroupId: string;
	chapterId: string | null;
}) {
	const glossary = useGlossaryTerms(memoryGroupId, chapterId);
	const [openTermId, setOpenTermId] = useState<string | null>(null);

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
						size="icon-sm"
						className="ml-auto"
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
						openTermId={openTermId}
						onOpenTermIdChange={setOpenTermId}
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
		</div>
	);
}
