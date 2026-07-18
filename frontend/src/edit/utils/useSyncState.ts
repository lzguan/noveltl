import { useCallback, useRef, useState } from "react";

export function identity<T>(value: T): T {
	return value;
}

export function copy<T>(value: T[]): T[] {
	return [...value];
}

export function useSyncState<T>(initialValue: T, copy: (value: T) => T = identity) {
	const [state, setState] = useState(initialValue);
	const stateRef = useRef(initialValue);

	const commit = useCallback(() => {
		setState(copy(stateRef.current));
	}, [copy]);
	return [state, stateRef, commit] as const;
}
