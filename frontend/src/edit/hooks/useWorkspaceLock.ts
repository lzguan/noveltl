import { useCallback, useRef, useState } from "react";

export type WorkspaceLock = Readonly<{
	message: string;
}>;

export type WorkspaceLockToken = symbol;

export function useWorkspaceLock() {
	const [workspaceLock, setWorkspaceLock] = useState<WorkspaceLock | null>(null);
	const activeTokenRef = useRef<WorkspaceLockToken | null>(null);

	const acquireLock = useCallback((message: string): WorkspaceLockToken | null => {
		if (activeTokenRef.current !== null) return null;

		const token = Symbol("workspace-lock");
		activeTokenRef.current = token;
		setWorkspaceLock({ message });
		return token;
	}, []);

	const releaseLock = useCallback((token: WorkspaceLockToken) => {
		if (activeTokenRef.current !== token) return;

		activeTokenRef.current = null;
		setWorkspaceLock(null);
	}, []);

	return { workspaceLock, acquireLock, releaseLock };
}
