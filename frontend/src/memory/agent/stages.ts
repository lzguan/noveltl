import type { StageConfig } from "@/api/models";

export type MemoryStageName = StageConfig["stageName"];

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
