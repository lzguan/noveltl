export type ChapterRef = {
	chapterId: string;
	chapterNum: number;
	chapterTitle: string;
};

export type ChapterPosition<T extends ChapterRef> = {
	current: T;
	prev: T | null;
	next: T | null;
};

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isUuid(value: string | undefined): value is string {
	return value !== undefined && UUID_PATTERN.test(value);
}

export function parseChapterNum(value: string | undefined): number | null {
	if (value === undefined || !/^\d{1,9}$/.test(value)) return null;
	return Number(value);
}

export function sortChapters<T extends ChapterRef>(chapters: readonly T[]): T[] {
	return [...chapters].sort((a, b) => a.chapterNum - b.chapterNum);
}

export function locateChapter<T extends ChapterRef>(
	chapters: readonly T[],
	chapterNum: number,
): ChapterPosition<T> | null {
	const sorted = sortChapters(chapters);
	const index = sorted.findIndex((chapter) => chapter.chapterNum === chapterNum);
	const current = sorted[index];
	if (current === undefined) return null;
	return {
		current,
		prev: sorted[index - 1] ?? null,
		next: sorted[index + 1] ?? null,
	};
}

export function chapterHref(novelId: string, chapterNum: number): string {
	return `/novel/${novelId}/${chapterNum}`;
}

export function chapterLabel(chapter: ChapterRef): string {
	const title = chapter.chapterTitle.trim();
	return title ? title : `Chapter ${chapter.chapterNum}`;
}

export function splitParagraphs(text: string): string[] {
	return text
		.split(/\r?\n/)
		.map((line) => line.trim())
		.filter((line) => line.length > 0);
}
