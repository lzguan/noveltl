import { useCallback, useRef, useState } from "react";
import type { LabelBase } from "@/api/models";

export type AutoLabelPreview = readonly LabelBase[];

export function useAutoLabelPreview() {
	const [enabled, setEnabledState] = useState(false);
	const [loading, setLoadingState] = useState(false);
	const [preview, setPreviewState] = useState<AutoLabelPreview | null>(null);
	const enabledRef = useRef(false);
	const loadingRef = useRef(false);
	const previewRef = useRef<AutoLabelPreview | null>(null);

	const setEnabled = useCallback((next: boolean) => {
		enabledRef.current = next;
		setEnabledState(next);

		if (!next) {
			loadingRef.current = false;
			setLoadingState(false);
			previewRef.current = null;
			setPreviewState(null);
		}
	}, []);

	const setLoading = useCallback((next: boolean) => {
		if (next && !enabledRef.current) return;

		loadingRef.current = next;
		setLoadingState(next);
		if (next) {
			previewRef.current = null;
			setPreviewState(null);
		}
	}, []);

	const setPreview = useCallback((next: AutoLabelPreview | null) => {
		if (next !== null && !enabledRef.current) return;

		const previewValue: AutoLabelPreview | null = next === null ? null : [...next];
		loadingRef.current = false;
		setLoadingState(false);
		previewRef.current = previewValue;
		setPreviewState(previewValue);
	}, []);

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
