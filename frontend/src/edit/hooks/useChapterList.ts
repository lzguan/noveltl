import { useCallback, useRef, useState } from "react";
import type { CProvId, ProvChapter } from "../controller/types/idTypes";

export function useChapterList() {
	const [chapterList, setChapterList] = useState<ProvChapter[]>([]); // sorted by chapterNum
	const chapterListRef = useRef<ProvChapter[]>([]); // sorted by chapterNum

	const addChapter = useCallback((chapter: ProvChapter) => {
		const idx = chapterListRef.current.findIndex((c) => chapter.chapterNum <= c.chapterNum);
		if (idx === -1) {
			chapterListRef.current.push(chapter);
		} else {
			chapterListRef.current.splice(idx, 0, chapter);
		}
		setChapterList([...chapterListRef.current]);
	}, []);

	const setChapter = useCallback((id: CProvId, chapter: ProvChapter) => {
		const idx = chapterListRef.current.findIndex((c) => c.chapterId === id);
		if (idx === -1) {
			console.warn(`Trying to set chapter with id ${id} that does not exist in chapter list`);
			return;
		}
		chapterListRef.current[idx] = chapter;
		setChapterList([...chapterListRef.current]);
	}, []);

	const removeChapter = useCallback((id: CProvId) => {
		const idx = chapterListRef.current.findIndex((c) => c.chapterId === id);
		if (idx === -1) {
			console.warn(
				`Trying to remove chapter with id ${id} that does not exist in chapter list`,
			);
			return;
		}
		chapterListRef.current.splice(idx, 1);
		setChapterList([...chapterListRef.current]);
	}, []);

	return { chapterList, addChapter, setChapter, removeChapter, chapterListRef };
}
