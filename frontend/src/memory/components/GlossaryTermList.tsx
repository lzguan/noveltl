import type { GlossaryTermSummary } from "@/api/models";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import type { Loadable, Page } from "@/lib/loadable";
import { cn } from "@/lib/utils";
import { useTermMemories } from "@/memory/hooks/useTermMemories";
import { ChevronDownIcon } from "lucide-react";
import { useState } from "react";
import { MemoryRow } from "./MemoryRow";
import { PageNavigation } from "./PageNavigation";

function GlossaryTermRow({
	memoryGroupId,
	term,
	chapterId,
	open,
	onExpandedChange,
}: {
	memoryGroupId: string;
	term: GlossaryTermSummary;
	chapterId: string | null;
	open: boolean;
	onExpandedChange: (open: boolean) => void;
}) {
	const termMemories = useTermMemories(memoryGroupId, term.termId, chapterId);

	function changeOpen(nextOpen: boolean) {
		onExpandedChange(nextOpen);
		if (nextOpen && termMemories.memories.status === "idle") {
			termMemories.loadMemories();
		}
	}

	return (
		<Collapsible open={open} onOpenChange={changeOpen} className="border-b">
			<CollapsibleTrigger className="flex w-full items-center gap-2 px-2 py-2 text-left text-sm hover:bg-muted/50">
				<ChevronDownIcon
					className={cn("size-4 shrink-0 transition-transform", open && "rotate-180")}
				/>
				<span className="min-w-0 flex-1 truncate font-medium">{term.term}</span>
				<span className="whitespace-nowrap text-xs text-muted-foreground">
					{term.associatedMemoryCount}{" "}
					{term.associatedMemoryCount === 1 ? "memory" : "memories"}
				</span>
				<Badge variant="outline">{term.reviewStatus}</Badge>
			</CollapsibleTrigger>
			<CollapsibleContent className="border-t bg-muted/20">
				{termMemories.memories.status === "idle" ||
				termMemories.memories.status === "loading" ? (
					<div aria-busy="true" className="flex flex-col gap-2 p-2">
						<Skeleton className="h-24 w-full" />
						<Skeleton className="h-24 w-full" />
					</div>
				) : termMemories.memories.status === "error" ? (
					<div className="flex flex-col items-start gap-2 p-3 text-sm text-destructive">
						<p>{termMemories.memories.message}</p>
						<Button variant="outline" size="sm" onClick={termMemories.reloadMemories}>
							Retry
						</Button>
					</div>
				) : termMemories.memories.data.items.length === 0 ? (
					<p className="p-3 text-sm text-muted-foreground">No associated memories.</p>
				) : (
					<div>
						{termMemories.memories.data.items.map(({ memory, terms }) => (
							<MemoryRow key={memory.memoryId} memory={memory} terms={terms} />
						))}
						<PageNavigation
							start={termMemories.memories.data.start}
							end={termMemories.memories.data.end}
							total={termMemories.memories.data.total}
							hasPrevious={termMemories.memories.data.hasPrevious}
							hasNext={termMemories.memories.data.hasNext}
							onPrevious={termMemories.loadPreviousPage}
							onNext={termMemories.loadNextPage}
						/>
					</div>
				)}
			</CollapsibleContent>
		</Collapsible>
	);
}

export function GlossaryTermList({
	terms,
	memoryGroupId,
	chapterId,
}: {
	terms: Loadable<Page<GlossaryTermSummary>>;
	memoryGroupId: string;
	chapterId: string | null;
}) {
	const [openTermId, setOpenTermId] = useState<string | null>(null);

	if (terms.status === "idle" || terms.status === "loading") {
		return (
			<div aria-busy="true" className="flex flex-col gap-2 p-2">
				<Skeleton className="h-10 w-full" />
				<Skeleton className="h-10 w-full" />
				<Skeleton className="h-10 w-full" />
			</div>
		);
	}
	if (terms.status === "error") return null;
	if (terms.data.items.length === 0) {
		return (
			<Empty>
				<EmptyHeader>
					<EmptyTitle>No glossary terms</EmptyTitle>
					<EmptyDescription>
						No terms match the current scope and search.
					</EmptyDescription>
				</EmptyHeader>
			</Empty>
		);
	}

	return (
		<div className="min-h-0 flex-1 overflow-y-auto">
			{terms.data.items.map((term) => (
				<GlossaryTermRow
					key={term.termId}
					memoryGroupId={memoryGroupId}
					term={term}
					chapterId={chapterId}
					open={openTermId === term.termId}
					onExpandedChange={(open) => setOpenTermId(open ? term.termId : null)}
				/>
			))}
		</div>
	);
}
