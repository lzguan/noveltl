import { Result, Schema } from "effect";

const MAX_CHAPTERS = 10_000;
const MAX_CHAPTER_TITLE_LENGTH = 255;

const ChapterUploadV1Schema = Schema.Struct({
	chapterContentText: Schema.String,
	chapterIsPublic: Schema.optional(Schema.Boolean),
	chapterNum: Schema.Number.check(Schema.isInt()),
	chapterTitle: Schema.optional(
		Schema.NullOr(Schema.String.check(Schema.isMaxLength(MAX_CHAPTER_TITLE_LENGTH))),
	),
});

const BulkChapterUploadV1Schema = Schema.Struct({
	chapters: Schema.Array(ChapterUploadV1Schema).check(
		Schema.isMinLength(1),
		Schema.isMaxLength(MAX_CHAPTERS),
	),
});

type ChapterUploadSummary = {
	chapterCount: number;
	draftCount: number;
	maxChapterNum: number;
	minChapterNum: number;
	publicCount: number;
};

type ChapterUploadParseResult =
	| { error: string; ok: false }
	| { ok: true; summary: ChapterUploadSummary };

function parseChapterUploadV1(text: string): ChapterUploadParseResult {
	let value: unknown;
	try {
		value = JSON.parse(text);
	} catch {
		return { error: "The selected file is not valid JSON.", ok: false };
	}

	const decoded = Schema.decodeUnknownResult(BulkChapterUploadV1Schema)(value);
	if (Result.isFailure(decoded)) {
		return {
			error: "The selected file does not match the V1 chapter upload format.",
			ok: false,
		};
	}

	const chapterNumbers = decoded.success.chapters.map((chapter) => chapter.chapterNum);
	const publicCount = decoded.success.chapters.filter(
		(chapter) => chapter.chapterIsPublic === true,
	).length;

	return {
		ok: true,
		summary: {
			chapterCount: decoded.success.chapters.length,
			draftCount: decoded.success.chapters.length - publicCount,
			maxChapterNum: Math.max(...chapterNumbers),
			minChapterNum: Math.min(...chapterNumbers),
			publicCount,
		},
	};
}

export { parseChapterUploadV1 };
export type { ChapterUploadParseResult, ChapterUploadSummary };
