// @vitest-environment node
/// <reference types="node" />

import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { parseChapterUploadV1 } from "./chapterUploadFile";

const STARFALL_UPLOAD_ARTIFACT = resolve(
	dirname(fileURLToPath(import.meta.url)),
	"../../../../backend/tests/test_data/artifacts/chapter-upload/v1/starfall.json",
);

describe("parseChapterUploadV1", () => {
	it("parses the shared Starfall V1 upload artifact", () => {
		const result = parseChapterUploadV1(readFileSync(STARFALL_UPLOAD_ARTIFACT, "utf8"));

		expect(result).toEqual({
			ok: true,
			summary: {
				chapterCount: 4,
				draftCount: 0,
				maxChapterNum: 4,
				minChapterNum: 1,
				publicCount: 4,
			},
		});
	});

	it("summarizes a valid upload document", () => {
		const result = parseChapterUploadV1(
			JSON.stringify({
				chapters: [
					{
						chapterContentText: "One",
						chapterIsPublic: true,
						chapterNum: 1,
						chapterTitle: "First",
					},
					{ chapterContentText: "", chapterNum: 4 },
				],
			}),
		);

		expect(result).toEqual({
			ok: true,
			summary: {
				chapterCount: 2,
				draftCount: 1,
				maxChapterNum: 4,
				minChapterNum: 1,
				publicCount: 1,
			},
		});
	});

	it("rejects malformed JSON", () => {
		expect(parseChapterUploadV1('{"chapters":')).toEqual({
			error: "The selected file is not valid JSON.",
			ok: false,
		});
	});

	it.each([
		{ chapters: [] },
		{ chapters: [{ chapterContentText: "Text", chapterNum: 1.5 }] },
		{ chapters: [{ chapterNum: 1 }] },
	])("rejects documents outside the V1 schema", (document) => {
		expect(parseChapterUploadV1(JSON.stringify(document))).toEqual({
			error: "The selected file does not match the V1 chapter upload format.",
			ok: false,
		});
	});
});
