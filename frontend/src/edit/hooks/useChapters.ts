import { useCallback, useRef } from "react";
import type { CProvId, ProvChapter } from "../controller/types/idTypes";
import { copy, useSyncState } from "../utils/useSyncState";

export type ChapterTab = {
	chapterId: CProvId;
	status: "loading" | "ready";
};

export function useChapters() {
	const [chapterList, chapterListRef, commitChapterList] = useSyncState<ProvChapter[]>([], copy); // sorted by chapterNum
	const [tabs, tabsRef, commitTabs] = useSyncState<ChapterTab[]>([], copy);
	const [activeChapterId, activeChapterIdRef, commitActiveChapterId] =
		useSyncState<CProvId | null>(null);
	const [openChapterContentIds, openChapterContentIdsRef, commitOpenChapterContentIds] =
		useSyncState<ReadonlyMap<string, string | null>>(new Map());
	const closingChapterIdsRef = useRef(new Set<CProvId>());

	const addChapter = useCallback(
		(chapter: ProvChapter) => {
			const idx = chapterListRef.current.findIndex((c) => chapter.chapterNum <= c.chapterNum);
			if (idx === -1) {
				chapterListRef.current.push(chapter);
			} else {
				chapterListRef.current.splice(idx, 0, chapter);
			}
			commitChapterList();
		},
		[chapterListRef, commitChapterList],
	);

	const setChapter = useCallback(
		(id: CProvId, chapter: ProvChapter) => {
			const idx = chapterListRef.current.findIndex((c) => c.chapterId === id);
			if (idx === -1) {
				console.warn(
					`Trying to set chapter with id ${id} that does not exist in chapter list`,
				);
				return;
			}
			chapterListRef.current[idx] = chapter;
			commitChapterList();
		},
		[chapterListRef, commitChapterList],
	);

	const updateTabs = useCallback(
		(next: ChapterTab[]) => {
			tabsRef.current = next;
			commitTabs();
		},
		[tabsRef, commitTabs],
	);

	const updateActive = useCallback(
		(chapterId: CProvId | null) => {
			activeChapterIdRef.current = chapterId;
			commitActiveChapterId();
		},
		[activeChapterIdRef, commitActiveChapterId],
	);

	const removeTab = useCallback(
		(chapterId: CProvId) => {
			const index = tabsRef.current.findIndex((tab) => tab.chapterId === chapterId);
			if (index === -1) return null;

			const wasActive = activeChapterIdRef.current === chapterId;
			const remaining = tabsRef.current.filter((tab) => tab.chapterId !== chapterId);
			const nextChapterId = wasActive
				? (remaining[index]?.chapterId ?? remaining[index - 1]?.chapterId ?? null)
				: activeChapterIdRef.current;
			updateTabs(remaining);
			if (wasActive) updateActive(nextChapterId);
			return { wasActive, nextChapterId };
		},
		[tabsRef, activeChapterIdRef, updateTabs, updateActive],
	);

	const removeChapter = useCallback(
		(id: CProvId) => {
			const idx = chapterListRef.current.findIndex((c) => c.chapterId === id);
			if (idx === -1) {
				console.warn(
					`Trying to remove chapter with id ${id} that does not exist in chapter list`,
				);
				return null;
			}
			chapterListRef.current.splice(idx, 1);
			commitChapterList();
			return removeTab(id);
		},
		[chapterListRef, commitChapterList, removeTab],
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
		chapterList,
		chapterListRef,
		addChapter,
		setChapter,
		removeChapter,
		tabs,
		tabsRef,
		updateTabs,
		removeTab,
		activeChapterId,
		activeChapterIdRef,
		updateActive,
		openChapterContentIds,
		setOpenChapterContentId,
		removeOpenChapterContentId,
		closingChapterIdsRef,
	};
}
