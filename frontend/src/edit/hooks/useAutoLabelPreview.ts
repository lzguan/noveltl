import { useCallback } from "react";
import type { LabelBase } from "@/api/models";
import { useSyncState } from "../utils/useSyncState";

export type AutoLabelPreview = readonly LabelBase[];

export function useAutoLabelPreview() {
	const [enabled, enabledRef, commitEnabled] = useSyncState(false);
	const [loading, loadingRef, commitLoading] = useSyncState(false);
	const [preview, previewRef, commitPreview] = useSyncState<AutoLabelPreview | null>(null);

	const setEnabled = useCallback(
		(next: boolean) => {
			enabledRef.current = next;
			commitEnabled();

			if (!next) {
				loadingRef.current = false;
				commitLoading();
				previewRef.current = null;
				commitPreview();
			}
		},
		[loadingRef, commitLoading, previewRef, commitPreview, enabledRef, commitEnabled],
	);

	const setLoading = useCallback(
		(next: boolean) => {
			if (next && !enabledRef.current) return;

			loadingRef.current = next;
			commitLoading();
			if (next) {
				previewRef.current = null;
				commitPreview();
			}
		},
		[loadingRef, commitLoading, previewRef, commitPreview, enabledRef],
	);

	const setPreview = useCallback(
		(next: AutoLabelPreview | null) => {
			if (next !== null && !enabledRef.current) return;

			const previewValue: AutoLabelPreview | null = next === null ? null : [...next];
			loadingRef.current = false;
			commitLoading();
			previewRef.current = previewValue;
			commitPreview();
		},
		[previewRef, commitPreview, enabledRef, loadingRef, commitLoading],
	);

	return {
		enabled,
		enabledRef,
		loading,
		loadingRef,
		preview,
		previewRef,
		setEnabled,
		setLoading,
		setPreview,
	};
}
