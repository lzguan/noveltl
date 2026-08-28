import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { MemoryJobBrowser } from "@/memory/agent/components/MemoryJobBrowser";
import { CreateMemoryGroupDialog } from "@/memory/components/CreateMemoryGroupDialog";
import { MemoryGroupSelector } from "@/memory/components/MemoryGroupSelector";
import { useMemoryGroupsContext } from "@/memory/context/MemoryGroupsContext";
import { useState } from "react";

export function MemoryAgentPanel({ novelId }: { novelId: string }) {
	const { groups, selectedGroupId, reloadGroups, selectGroup, addAndSelectGroup } =
		useMemoryGroupsContext();
	const [createGroupOpen, setCreateGroupOpen] = useState(false);

	if (groups.status === "idle" || groups.status === "loading") {
		return (
			<div aria-busy="true" className="flex h-full flex-col gap-2 p-2">
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

	return (
		<div className="flex h-full min-h-0 flex-col">
			{groups.data.length === 0 || selectedGroupId === null ? (
				<Empty>
					<EmptyHeader>
						<EmptyTitle>No memory groups</EmptyTitle>
						<EmptyDescription>
							Create a memory group before creating agent jobs.
						</EmptyDescription>
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
					<MemoryJobBrowser key={selectedGroupId} memoryGroupId={selectedGroupId} />
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
