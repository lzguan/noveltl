import { MemoryType } from "@/api/models";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useMemoryBrowser } from "@/memory/hooks/useMemoryBrowser";
import { RefreshCwIcon } from "lucide-react";
import { useEffect } from "react";
import { MemoryRow } from "./MemoryRow";
import { PageNavigation } from "./PageNavigation";

const ALL_MEMORY_TYPES = "all";

function isMemoryType(value: string): value is MemoryType {
	return Object.values(MemoryType).some((candidate) => candidate === value);
}

export function MemoryBrowser({
	memoryGroupId,
	chapterId,
}: {
	memoryGroupId: string;
	chapterId: string | null;
}) {
	const browser = useMemoryBrowser(memoryGroupId, chapterId);

	useEffect(() => {
		// Mounting this keyed browser establishes a new group/chapter query context.
		// Filter and pagination changes issue their requests directly from events.
		browser.loadMemories();
		// oxlint-disable-next-line react-hooks/exhaustive-deps
	}, []);

	return (
		<div className="flex min-h-0 flex-1 flex-col">
			<div className="flex flex-wrap items-center justify-between gap-3 border-b p-2">
				<div className="flex items-center gap-2">
					<Checkbox
						id="memory-from-all-chapters"
						checked={browser.fromAllChapters}
						onCheckedChange={(checked) => browser.setFromAllChapters(checked === true)}
					/>
					<Label htmlFor="memory-from-all-chapters" className="text-xs">
						From all chapters
					</Label>
				</div>
				<div className="flex items-center gap-2">
					<Label htmlFor="memory-type-filter" className="text-xs text-muted-foreground">
						Type
					</Label>
					<Select
						value={browser.memoryType ?? ALL_MEMORY_TYPES}
						onValueChange={(value) => {
							if (value === ALL_MEMORY_TYPES) browser.setMemoryType(null);
							else if (isMemoryType(value)) browser.setMemoryType(value);
						}}
					>
						<SelectTrigger id="memory-type-filter" size="sm" className="w-32">
							<SelectValue />
						</SelectTrigger>
						<SelectContent>
							<SelectItem value={ALL_MEMORY_TYPES}>All types</SelectItem>
							<SelectItem value={MemoryType.fact}>Fact</SelectItem>
							<SelectItem value={MemoryType.event}>Event</SelectItem>
							<SelectItem value={MemoryType.def}>Definition</SelectItem>
							<SelectItem value={MemoryType.rel}>Relation</SelectItem>
						</SelectContent>
					</Select>
					<Button
						variant="ghost"
						size="icon-sm"
						aria-label="Refresh memories"
						title="Refresh memories"
						disabled={browser.memories.status === "loading"}
						onClick={browser.reloadMemories}
					>
						<RefreshCwIcon />
					</Button>
				</div>
			</div>

			{browser.memories.status === "idle" &&
			chapterId === null &&
			!browser.fromAllChapters ? (
				<Empty>
					<EmptyHeader>
						<EmptyTitle>No chapter open</EmptyTitle>
						<EmptyDescription>
							Open a chapter or select From all chapters to browse memories.
						</EmptyDescription>
					</EmptyHeader>
				</Empty>
			) : browser.memories.status === "idle" || browser.memories.status === "loading" ? (
				<div aria-busy="true" className="flex flex-col gap-2 p-2">
					<Skeleton className="h-20 w-full" />
					<Skeleton className="h-20 w-full" />
					<Skeleton className="h-20 w-full" />
				</div>
			) : browser.memories.status === "error" ? (
				<div className="flex flex-col items-start gap-2 p-3 text-sm text-destructive">
					<p>{browser.memories.message}</p>
					<Button variant="outline" size="sm" onClick={browser.reloadMemories}>
						Retry
					</Button>
				</div>
			) : browser.memories.data.items.length === 0 ? (
				<Empty>
					<EmptyHeader>
						<EmptyTitle>No memories</EmptyTitle>
						<EmptyDescription>
							No memories match the current chapter scope and type filter.
						</EmptyDescription>
					</EmptyHeader>
				</Empty>
			) : (
				<div className="flex min-h-0 flex-1 flex-col">
					<div className="min-h-0 flex-1 overflow-y-auto">
						{browser.memories.data.items.map((memory) => (
							<MemoryRow key={memory.memoryId} memory={memory} />
						))}
					</div>
					<PageNavigation
						start={browser.memories.data.start}
						end={browser.memories.data.end}
						total={browser.memories.data.total}
						hasPrevious={browser.memories.data.hasPrevious}
						hasNext={browser.memories.data.hasNext}
						onPrevious={browser.loadPreviousPage}
						onNext={browser.loadNextPage}
					/>
				</div>
			)}
		</div>
	);
}
