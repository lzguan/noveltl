import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { GlossaryBrowser } from "@/memory/components/GlossaryBrowser";
import { MemoryBrowser } from "@/memory/components/MemoryBrowser";
import { MemoryGroupSelector } from "@/memory/components/MemoryGroupSelector";
import { PluginSelector, type MemoryView } from "@/memory/components/PluginSelector";
import { useMemoryGroups } from "@/memory/hooks/useMemoryGroups";
import { useEffect, useState } from "react";

export function MemoryPanel({
	novelId,
	chapterId,
}: {
	novelId: string;
	/** Server id of the currently open chapter, or null when no chapter is open. */
	chapterId: string | null;
}) {
	const { groups, selectedGroupId, loadGroups, reloadGroups, selectGroup } =
		useMemoryGroups(novelId);
	const [view, setView] = useState<MemoryView>("memories");

	useEffect(() => {
		loadGroups();
	}, [loadGroups]);

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

	if (groups.data.length === 0 || selectedGroupId === null) {
		return (
			<Empty>
				<EmptyHeader>
					<EmptyTitle>No memory groups</EmptyTitle>
					<EmptyDescription>This novel has no memory groups yet.</EmptyDescription>
				</EmptyHeader>
			</Empty>
		);
	}

	const browserKey = `${selectedGroupId}:${chapterId ?? "no-chapter"}`;

	return (
		<div className="flex h-full min-h-0 flex-col">
			<MemoryGroupSelector
				groups={groups.data}
				selectedGroupId={selectedGroupId}
				onSelect={selectGroup}
			/>
			<PluginSelector value={view} onChange={setView} />
			{view === "memories" ? (
				<MemoryBrowser
					key={browserKey}
					memoryGroupId={selectedGroupId}
					chapterId={chapterId}
				/>
			) : (
				<GlossaryBrowser
					key={browserKey}
					memoryGroupId={selectedGroupId}
					chapterId={chapterId}
				/>
			)}
		</div>
	);
}
