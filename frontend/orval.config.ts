import { readFile, writeFile } from "node:fs/promises";
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
		hooks: {
			afterAllFilesWrite: async () => {
				// Orval widens separator weights to number, but their Effect schema
				// accepts only 1 | 2 | 3. Preserve literal types after regeneration.
				const path = new URL(
					"./src/api/endpoints/default/default.effect.ts",
					import.meta.url,
				);
				const source = await readFile(path, "utf8");
				await writeFile(
					path,
					source.replace(
						/(export const \w+SeparatorsDefault = \{[^\r\n]*\});/g,
						"$1 as const;",
					),
				);
			},
		},
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
