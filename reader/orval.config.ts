import { defineConfig } from "orval";

export default defineConfig({
	backend: {
		input: {
			target: "../backend/openapi.yaml",
			// Generate only the operations the reader calls; add an ID here when a
			// route needs another endpoint.
			filters: {
				mode: "include",
				operationIds: [
					"read_novels_novels_get",
					"read_novel_novels__novelId__get",
					"read_chapters_by_novel_chapters_get",
					"read_chapter_content_chapters__chapterId__content_get",
				],
			},
		},
		output: {
			mode: "tags-split",
			client: "fetch",
			target: "app/api/endpoints",
			schemas: "app/api/models",
			override: {
				fetch: {
					includeHttpResponseReturnType: false,
				},
				mutator: {
					path: "./app/api/backend-fetch.ts",
					name: "backendFetch",
				},
			},
		},
	},
});
