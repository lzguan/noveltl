import { useMemoryGroups } from "@/memory/hooks/useMemoryGroups";
import { createContext, useContext, useEffect } from "react";
import type { ReactNode } from "react";

const MemoryGroupsContext = createContext<ReturnType<typeof useMemoryGroups> | null>(null);

/** Shares one novel's memory-group list and selection between right-panel views. */
export function MemoryGroupsProvider({
	novelId,
	children,
}: {
	novelId: string;
	children: ReactNode;
}) {
	const memoryGroups = useMemoryGroups(novelId);
	const { loadGroups } = memoryGroups;

	useEffect(() => {
		loadGroups();
	}, [loadGroups]);

	return (
		<MemoryGroupsContext.Provider value={memoryGroups}>{children}</MemoryGroupsContext.Provider>
	);
}

export function useMemoryGroupsContext() {
	const memoryGroups = useContext(MemoryGroupsContext);
	if (memoryGroups === null) {
		throw new Error("useMemoryGroupsContext must be used inside MemoryGroupsProvider.");
	}
	return memoryGroups;
}
