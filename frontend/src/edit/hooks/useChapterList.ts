import { useCallback } from "react";
import type { CProvId, ProvChapter } from "../controller/types/idTypes";
import { useSyncState } from "../utils/useSyncState";

function copyList<T>(list: readonly T[]): T[] {
	return [...list];
}

export function useChapterList() {
	const [chapterList, chapterListRef, commitChapterList] = useSyncState<ProvChapter[]>(
		[],
		copyList,
	); // sorted by chapterNum

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

	const removeChapter = useCallback(
		(id: CProvId) => {
			const idx = chapterListRef.current.findIndex((c) => c.chapterId === id);
			if (idx === -1) {
				console.warn(
					`Trying to remove chapter with id ${id} that does not exist in chapter list`,
				);
				return;
			}
			chapterListRef.current.splice(idx, 1);
			commitChapterList();
		},
		[chapterListRef, commitChapterList],
	);

	return { chapterList, addChapter, setChapter, removeChapter, chapterListRef };
}
