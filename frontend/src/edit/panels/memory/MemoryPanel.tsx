import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { ConventionsBrowser } from "@/memory/components/ConventionsBrowser";
import { CreateMemoryGroupDialog } from "@/memory/components/CreateMemoryGroupDialog";
import { GlossaryBrowser } from "@/memory/components/GlossaryBrowser";
import { MemoryBrowser } from "@/memory/components/MemoryBrowser";
import { MemoryGroupSelector } from "@/memory/components/MemoryGroupSelector";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useMemoryGroupsContext } from "@/memory/context/MemoryGroupsContext";
import { useState } from "react";

const MEMORY_VIEWS = [
	{ value: "memories", label: "All" },
	{ value: "glossary", label: "Glossary" },
	{ value: "translations", label: "Terms" },
	{ value: "conventions", label: "Conventions" },
] as const;

type MemoryView = (typeof MEMORY_VIEWS)[number]["value"];

function isMemoryView(value: string): value is MemoryView {
	return MEMORY_VIEWS.some((option) => option.value === value);
}

export function MemoryPanel({
	novelId,
	chapterId,
	chapterNum,
	chapterContentId,
}: {
	novelId: string;
	/** Server id of the currently open chapter, or null when no chapter is open. */
	chapterId: string | null;
	/** Number of the currently open chapter, or null when no chapter is open. */
	chapterNum: number | null;
	/** Server id of the active saved chapter content, or null while unavailable. */
	chapterContentId: string | null;
}) {
	const { groups, selectedGroupId, reloadGroups, selectGroup, addAndSelectGroup } =
		useMemoryGroupsContext();
	const [view, setView] = useState<MemoryView>("memories");
	// Views are mounted on first visit rather than all at once.
	const [visitedViews, setVisitedViews] = useState<ReadonlySet<MemoryView>>(
		() => new Set(["memories"]),
	);
	const [createGroupOpen, setCreateGroupOpen] = useState(false);

	if (groups.status === "idle" || groups.status === "loading") {
		return (
			<div aria-busy="true" className="flex h-full flex-col gap-2 p-2">
				<Skeleton className="h-12 w-full" />
				<Skeleton className="h-12 w-full" />
				<Skeleton className="h-24 w-full" />
			</div>
		);
	}

	if (groups.status === "error") {
		return (
			<div className="flex flex-col items-start gap-2 p-3 text-sm text-destructive">
				<p>{groups.message}</p>
				<Button variant="outline" size="sm" onClick={reloadGroups}>
					Retry
				</Button>
			</div>
		);
	}

	const browserKey = `${selectedGroupId ?? "no-group"}:${chapterId ?? "no-chapter"}`;

	return (
		<div className="flex h-full min-h-0 flex-col">
			{groups.data.length === 0 || selectedGroupId === null ? (
				<Empty>
					<EmptyHeader>
						<EmptyTitle>No memory groups</EmptyTitle>
						<EmptyDescription>This novel has no memory groups yet.</EmptyDescription>
					</EmptyHeader>
					<Button size="sm" onClick={() => setCreateGroupOpen(true)}>
						Create memory group
					</Button>
				</Empty>
			) : (
				<>
					<MemoryGroupSelector
						groups={groups.data}
						selectedGroupId={selectedGroupId}
						onSelect={selectGroup}
						onCreate={() => setCreateGroupOpen(true)}
					/>
					<Tabs
						value={view}
						onValueChange={(value) => {
							if (!isMemoryView(value)) return;
							setView(value);
							setVisitedViews((visited) => new Set(visited).add(value));
						}}
						className="min-h-0 flex-1 gap-0"
					>
						<TabsList
							variant="line"
							className="w-full shrink-0 justify-start border-b px-1 group-data-horizontal/tabs:h-auto"
						>
							{MEMORY_VIEWS.map((option) => (
								<TabsTrigger
									key={option.value}
									value={option.value}
									className="flex-none"
								>
									{option.label}
								</TabsTrigger>
							))}
						</TabsList>
						{MEMORY_VIEWS.filter((option) => visitedViews.has(option.value)).map(
							(option) => (
								// Visited views stay mounted so their filters and pages
								// survive switching tabs; the keys still reset them when the
								// group or chapter changes.
								<TabsContent
									key={option.value}
									value={option.value}
									forceMount
									hidden={view !== option.value}
									className="flex min-h-0 flex-1 flex-col"
								>
									{option.value === "memories" ? (
										<MemoryBrowser
											key={browserKey}
											memoryGroupId={selectedGroupId}
											chapterId={chapterId}
											chapterNum={chapterNum}
										/>
									) : option.value === "conventions" ? (
										<ConventionsBrowser
											key={selectedGroupId}
											memoryGroupId={selectedGroupId}
										/>
									) : (
										<GlossaryBrowser
											key={browserKey}
											memoryGroupId={selectedGroupId}
											chapterId={chapterId}
											chapterNum={chapterNum}
											chapterContentId={chapterContentId}
											view={option.value}
										/>
									)}
								</TabsContent>
							),
						)}
					</Tabs>
				</>
			)}
			{createGroupOpen && (
				<CreateMemoryGroupDialog
					novelId={novelId}
					closeDialog={() => setCreateGroupOpen(false)}
					addMemoryGroup={addAndSelectGroup}
				/>
			)}
		</div>
	);
}
