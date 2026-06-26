import { defineConfig } from "orval";

export default defineConfig({
	// HTTP client generation
	openapi: {
		input: {
			target: "../backend/openapi.yaml",
		},
		output: {
			mode: "tags-split",
			client: "fetch",
			target: "src/api/endpoints",
			schemas: "src/api/models",
			baseUrl: "/api",
			override: {
				mutator: {
					path: "./src/api/custom-fetch.ts",
					name: "customFetch",
				},
			},
		},
	},
	// Effect schema generation
	openapiEffect: {
		input: {
			target: "../backend/openapi.yaml",
		},
		output: {
			mode: "tags-split",
			client: "effect",
			target: "src/api/endpoints",
			fileExtension: ".effect.ts",
			override: {
				effect: {
					generateEachHttpStatus: true,
				},
			},
		},
	},
});
