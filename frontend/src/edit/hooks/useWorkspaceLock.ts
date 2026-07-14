import { useCallback, useRef, useState } from "react";

export type WorkspaceLock = Readonly<{
	message: string;
}>;

export type WorkspaceLockToken = symbol;

export type AcquireWorkspaceLock = (message: string) => WorkspaceLockToken | null;
export type ReleaseWorkspaceLock = (token: WorkspaceLockToken) => void;

export function useWorkspaceLock() {
	const [workspaceLock, setWorkspaceLock] = useState<WorkspaceLock | null>(null);
	const activeTokenRef = useRef<WorkspaceLockToken | null>(null);

	const acquireLock = useCallback<AcquireWorkspaceLock>((message) => {
		if (activeTokenRef.current !== null) return null;

		const token = Symbol("workspace-lock");
		activeTokenRef.current = token;
		setWorkspaceLock({ message });
		return token;
	}, []);

	const releaseLock = useCallback<ReleaseWorkspaceLock>((token) => {
		if (activeTokenRef.current !== token) return;

		activeTokenRef.current = null;
		setWorkspaceLock(null);
	}, []);

	return { workspaceLock, acquireLock, releaseLock };
}
