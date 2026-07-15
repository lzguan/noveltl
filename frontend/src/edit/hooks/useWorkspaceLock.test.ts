import { act, renderHook } from "@testing-library/react";
import { useWorkspaceLock, type WorkspaceLockToken } from "./useWorkspaceLock";

describe("useWorkspaceLock", () => {
	it("acquires and releases a workspace lock", () => {
		const { result } = renderHook(() => useWorkspaceLock());
		let token: WorkspaceLockToken | null = null;

		act(() => {
			token = result.current.acquireLock("Promoting labels...");
		});

		expect(token).not.toBeNull();
		expect(result.current.workspaceLock).toEqual({ message: "Promoting labels..." });

		act(() => {
			if (token !== null) result.current.releaseLock(token);
		});

		expect(result.current.workspaceLock).toBeNull();
	});

	it("rejects a second acquisition while locked", () => {
		const { result } = renderHook(() => useWorkspaceLock());
		let secondToken: WorkspaceLockToken | null = null;

		act(() => {
			result.current.acquireLock("First operation");
			secondToken = result.current.acquireLock("Second operation");
		});

		expect(secondToken).toBeNull();
		expect(result.current.workspaceLock).toEqual({ message: "First operation" });
	});

	it("ignores a release from a stale or foreign token", () => {
		const { result } = renderHook(() => useWorkspaceLock());
		let firstToken: WorkspaceLockToken | null = null;
		let secondToken: WorkspaceLockToken | null = null;

		act(() => {
			firstToken = result.current.acquireLock("First operation");
		});

		act(() => {
			result.current.releaseLock(Symbol("foreign"));
		});
		expect(result.current.workspaceLock).toEqual({ message: "First operation" });

		act(() => {
			if (firstToken !== null) result.current.releaseLock(firstToken);
			secondToken = result.current.acquireLock("Second operation");
		});

		act(() => {
			if (firstToken !== null) result.current.releaseLock(firstToken);
		});

		expect(secondToken).not.toBeNull();
		expect(result.current.workspaceLock).toEqual({ message: "Second operation" });
	});
});
