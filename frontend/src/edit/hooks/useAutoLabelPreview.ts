import { useCallback } from "react";
import type { LabelBase } from "@/api/models";
import { useSyncState } from "../utils/useSyncState";

export type AutoLabelPreview = readonly LabelBase[];

export function useAutoLabelPreview() {
	const [enabled, enabledRef, commitEnabled] = useSyncState(false);
	const [loading, loadingRef, commitLoading] = useSyncState(false);
	const [preview, previewRef, commitPreview] = useSyncState<AutoLabelPreview | null>(null);
	const [openChapterContentIds, openChapterContentIdsRef, commitOpenChapterContentIds] =
		useSyncState<ReadonlyMap<string, string | null>>(new Map());

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

	const setOpenChapterContentId = useCallback(
		(chapterServId: string, chapterContentServId: string | null) => {
			if (
				openChapterContentIdsRef.current.has(chapterServId) &&
				openChapterContentIdsRef.current.get(chapterServId) === chapterContentServId
			) {
				return;
			}
			const next = new Map(openChapterContentIdsRef.current);
			next.set(chapterServId, chapterContentServId);
			openChapterContentIdsRef.current = next;
			commitOpenChapterContentIds();
		},
		[openChapterContentIdsRef, commitOpenChapterContentIds],
	);

	const removeOpenChapterContentId = useCallback(
		(chapterServId: string) => {
			if (!openChapterContentIdsRef.current.has(chapterServId)) return;
			const next = new Map(openChapterContentIdsRef.current);
			next.delete(chapterServId);
			openChapterContentIdsRef.current = next;
			commitOpenChapterContentIds();
		},
		[openChapterContentIdsRef, commitOpenChapterContentIds],
	);

	return {
		enabled,
		enabledRef,
		loading,
		loadingRef,
		preview,
		previewRef,
		openChapterContentIds,
		setEnabled,
		setLoading,
		setPreview,
		setOpenChapterContentId,
		removeOpenChapterContentId,
	};
}
