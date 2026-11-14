import { defineConfig } from "orval";

export default defineConfig({
	backend: {
		input: {
			target: "../backend/openapi.yaml",
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
