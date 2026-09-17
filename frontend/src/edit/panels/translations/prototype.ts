import type { RJSFSchema } from "@rjsf/utils";

type ComponentType = "Chapter" | "Memories";
export type Action = {
	id: string;
	label: string;
	inputs: ComponentType[];
	outputs: ComponentType[];
	first: boolean;
	schema: RJSFSchema;
};
const inference = {
	model: {
		type: "string",
		title: "Model",
		enum: ["qwen-plus", "qwen-flash"],
		default: "qwen-plus",
	},
	instructions: { type: "string", title: "Instructions", default: "" },
	temperature: { type: "number", title: "Temperature", minimum: 0 },
	max_output_tokens: { type: "integer", title: "Maximum output tokens", minimum: 1 },
} satisfies NonNullable<RJSFSchema["properties"]>;
const retrieval = {
	exclude_current_chapter: {
		type: "boolean",
		title: "Exclude memories starting at this chapter",
		default: true,
	},
} satisfies NonNullable<RJSFSchema["properties"]>;
// Mock the future action metadata endpoint; forms and compatibility share this catalog.
export const actions: Action[] = [
	{
		id: "translate",
		label: "Translate",
		inputs: ["Chapter"],
		outputs: ["Chapter"],
		first: true,
		schema: {
			type: "object",
			required: ["model", "target_language"],
			properties: {
				...inference,
				target_language: {
					type: "string",
					title: "Target language",
					default: "English",
					minLength: 1,
				},
			},
		},
	},
	{
		id: "translate_with_memories",
		label: "Translate with memories",
		inputs: ["Chapter", "Memories"],
		outputs: ["Chapter"],
		first: true,
		schema: {
			type: "object",
			required: ["model", "target_language"],
			properties: {
				...inference,
				...retrieval,
				target_language: {
					type: "string",
					title: "Target language",
					default: "English",
					minLength: 1,
				},
			},
		},
	},
	{
		id: "prune_memories",
		label: "Prune memories",
		inputs: ["Chapter", "Memories"],
		outputs: ["Memories"],
		first: true,
		schema: { type: "object", required: ["model"], properties: { ...inference, ...retrieval } },
	},
	{
		id: "combine_chapter",
		label: "Combine chapter",
		inputs: ["Memories"],
		outputs: ["Chapter", "Memories"],
		first: false,
		schema: { type: "object", properties: {} },
	},
];
export type Stage = { id: string; action: Action; config: Record<string, unknown> };
export type BatchState =
	| "Not started"
	| "Running"
	| "Interrupted"
	| "Failed"
	| "Cancelled"
	| "Complete";
export type Batch = { id: number; completed: number; state: BatchState; error?: string };
export type Job = {
	id: string;
	title: string;
	start: number;
	end: number;
	memoryGroup: string;
	stages: Stage[];
	batches: Batch[];
};
export type Control = "Start" | "Resume" | "Retry" | "Cancel";
export const controls: Control[] = ["Start", "Resume", "Retry", "Cancel"];
export function eligible(batch: Batch, control: Control) {
	switch (control) {
		case "Start":
			return batch.state === "Not started";
		case "Resume":
			return batch.state === "Interrupted";
		case "Retry":
			return batch.state === "Failed" || batch.state === "Cancelled";
		case "Cancel":
			return batch.state !== "Complete" && batch.state !== "Cancelled";
	}
}
export function demoJobs(): Job[] {
	const stages = actions
		.filter((action) => action.id !== "translate")
		.sort(
			(a, b) =>
				["prune_memories", "combine_chapter", "translate_with_memories"].indexOf(a.id) -
				["prune_memories", "combine_chapter", "translate_with_memories"].indexOf(b.id),
		)
		.map((action) => ({
			id: action.id,
			action,
			config: { model: "qwen-plus", target_language: "English" },
		}));
	return [
		{
			id: "demo-running",
			title: "Job #12",
			start: 1,
			end: 500,
			memoryGroup: "Main glossary",
			stages,
			batches: [
				{ id: 1, completed: 3, state: "Complete" },
				{ id: 2, completed: 2, state: "Running" },
				{
					id: 3,
					completed: 1,
					state: "Failed",
					error: "Could not download the preceding stage output.",
				},
				{ id: 4, completed: 0, state: "Interrupted" },
				{ id: 5, completed: 0, state: "Not started" },
			],
		},
		{
			id: "demo-complete",
			title: "Job #11",
			start: 1,
			end: 100,
			memoryGroup: "Main glossary",
			stages,
			batches: [{ id: 1, completed: 3, state: "Complete" }],
		},
	];
}
