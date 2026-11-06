import type { JobParams } from "@/api/models";

export type MemoryStageName = "record_memories" | "summarize_conventions" | "translate_terms";

export const MEMORY_STAGE_LABELS: Record<MemoryStageName, string> = {
	record_memories: "Record memories",
	summarize_conventions: "Summarize conventions",
	translate_terms: "Translate terms",
};

/** Lowercase task noun, e.g. "the recording task". */
export const MEMORY_STAGE_TASK_NOUNS: Record<MemoryStageName, string> = {
	record_memories: "recording",
	summarize_conventions: "conventions",
	translate_terms: "term translation",
};

/** Mirrors backend `resolve_stages`: task stage numbers index this list. */
export function memoryJobStageNames(params: JobParams): MemoryStageName[] {
	if (params.version === 1) return ["record_memories"];
	const stages: MemoryStageName[] = [];
	if (params.recordMemories) stages.push("record_memories");
	if (params.summarizeConventions) stages.push("summarize_conventions");
	if (params.translateTerms) stages.push("translate_terms");
	return stages;
}
