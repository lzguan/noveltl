import { defineConfig } from "orval";

export default defineConfig({
	readerApi: {
		input: {
			target: "../reader-api/openapi.yaml",
			// Generate only the operations the reader calls; add an ID here when a
			// route needs another endpoint.
			filters: {
				mode: "include",
				operationIds: [
					"list_novels",
					"get_novel",
					"list_novel_chapters",
					"get_novel_chapter",
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
