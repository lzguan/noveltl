export type ChapterRef = {
	chapterNum: number;
	title: string;
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

export function chapterHref(novelId: string, chapterNum: number): string {
	return `/novel/${novelId}/${chapterNum}`;
}

export function chapterLabel(chapter: ChapterRef): string {
	const title = chapter.title.trim();
	return title ? title : `Chapter ${chapter.chapterNum}`;
}

export function splitParagraphs(text: string): string[] {
	return text
		.split(/\r?\n/)
		.map((line) => line.trim())
		.filter((line) => line.length > 0);
}
