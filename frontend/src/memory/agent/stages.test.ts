// @vitest-environment node

import type { JobParams } from "@/api/models";
import { memoryJobStageNames, type MemoryStageName } from "./stages";

const recording = { modelName: "deepseek:deepseek-v4-flash-low", toolsets: {} } as const;
const naming = { modelName: "deepseek:deepseek-v4-flash-low" } as const;
const conventions = { modelName: "deepseek:deepseek-v4-flash-low" } as const;
const cases: { name: string; params: JobParams; expected: MemoryStageName[] }[] = [
	{
		name: "V1 recording",
		params: { version: 1, ...recording },
		expected: ["record_memories"],
	},
	{
		name: "V2 recording only",
		params: { version: 2, recordMemories: recording, translateTerms: null },
		expected: ["record_memories"],
	},
	{
		name: "V2 naming only at stage zero",
		params: { version: 2, recordMemories: null, translateTerms: naming },
		expected: ["translate_terms"],
	},
	{
		name: "V2 recording followed by naming",
		params: { version: 2, recordMemories: recording, translateTerms: naming },
		expected: ["record_memories", "translate_terms"],
	},
	{
		name: "V2 conventions between recording and naming",
		params: {
			version: 2,
			recordMemories: recording,
			summarizeConventions: conventions,
			translateTerms: naming,
		},
		expected: ["record_memories", "summarize_conventions", "translate_terms"],
	},
];

it.each(cases)("resolves task stage names for $name", ({ params, expected }) => {
	expect(memoryJobStageNames(params)).toEqual(expected);
});
