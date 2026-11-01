import type { JobParams } from "@/api/models";

export type MemoryStageName = "record_memories" | "translate_terms";

export function memoryJobStageNames(params: JobParams): MemoryStageName[] {
	if (params.version === 1) return ["record_memories"];
	const stages: MemoryStageName[] = [];
	if (params.recordMemories) stages.push("record_memories");
	if (params.translateTerms) stages.push("translate_terms");
	return stages;
}
