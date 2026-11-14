// @vitest-environment node
import type { TranslationInputPort, TranslationPipelineCheck } from "@/api/models";
import { layout } from "./layout";

const chapter = { stream: "chapter", type: "chapter" } as const;
const memories = { stream: "memories", type: "memories" } as const;

function input(stream: "chapter" | "memories", source: number): TranslationInputPort {
	return {
		stream,
		type: stream,
		source,
		sourceType: stream,
		link: "linked",
		optional: stream === "memories",
		drops: false,
	};
}

it("preserves lane order and explicit producers across bypassed stages and lane ends", () => {
	const check: TranslationPipelineCheck = {
		stages: [
			{ action: "load_inputs", inputs: [], outputs: [chapter, memories], warning: null },
			{
				action: "prune_memories",
				inputs: [input("chapter", 0), input("memories", 0)],
				outputs: [memories],
				warning: null,
			},
			{
				action: "translate",
				inputs: [input("chapter", 0), input("memories", 1)],
				outputs: [chapter],
				warning: null,
			},
			{
				action: "translate",
				inputs: [input("chapter", 2), input("memories", 1)],
				outputs: [chapter],
				warning: null,
			},
		],
		ends: [
			{ ...chapter, source: 3 },
			{ ...memories, source: 1 },
		],
		addable: [],
	};
	const drawing = layout(check);
	expect(drawing.lanes.map((lane) => lane.stream)).toEqual(["chapter", "memories"]);
	expect(drawing.lanes[0].x).toBeLessThan(drawing.lanes[1].x);
	expect(
		drawing.segments.filter((segment) => segment.kind === "input" && segment.row === 3),
	).toMatchObject([
		{ stream: "chapter", source: 2, y1: drawing.rows[2].bottom, y2: drawing.rows[3].y },
		{ stream: "memories", source: 1, y1: drawing.rows[1].bottom, y2: drawing.rows[3].y },
	]);
	expect(drawing.segments.filter((segment) => segment.kind === "end")).toMatchObject([
		{ stream: "chapter", source: 3, y1: drawing.rows[3].bottom },
		{ stream: "memories", source: 1, y1: drawing.rows[1].bottom },
	]);
	for (const segment of drawing.segments.filter((segment) => segment.kind === "end"))
		expect(segment.y2).toBeGreaterThan(drawing.rows[3].bottom);
});

it("shows broken stubs and absent optional ports while a warning stage feeds nothing", () => {
	const check: TranslationPipelineCheck = {
		stages: [
			{ action: "load_inputs", inputs: [], outputs: [chapter], warning: null },
			{
				action: "prune_memories",
				inputs: [
					{
						...input("memories", 0),
						optional: false,
						link: "broken",
						source: null,
						sourceType: null,
					},
				],
				outputs: [memories],
				warning: "requires memories",
			},
			{
				action: "translate",
				inputs: [
					input("chapter", 0),
					{ ...input("memories", 0), link: "absent", source: null, sourceType: null },
				],
				outputs: [chapter],
				warning: null,
			},
		],
		ends: [{ ...chapter, source: 2 }],
		addable: [],
	};
	const drawing = layout(check);
	expect(drawing.stubs).toEqual([
		{
			stream: "memories",
			row: 1,
			x: drawing.lanes[1].x,
			y1: drawing.rows[1].y - 20,
			y2: drawing.rows[1].y,
		},
	]);
	expect(drawing.ports).toContainEqual(
		expect.objectContaining({ row: 2, stream: "memories", link: "absent", optional: true }),
	);
	expect(drawing.segments.some((segment) => segment.stream === "memories")).toBe(false);
	expect(drawing.segments.some((segment) => segment.source === 1)).toBe(false);
	expect(drawing.rows[1].hasWarning).toBe(true);
	expect(drawing.ports).toContainEqual(
		expect.objectContaining({ row: 1, kind: "output", stream: "memories" }),
	);
});

it("keeps incompatible links and drops exactly as supplied, including later rewrites", () => {
	const check: TranslationPipelineCheck = {
		stages: [
			{ action: "load_inputs", inputs: [], outputs: [chapter], warning: null },
			{
				action: "consume",
				inputs: [{ ...input("chapter", 0), drops: true }],
				outputs: [],
				warning: null,
			},
			{ action: "write", inputs: [], outputs: [chapter], warning: null },
			{
				action: "read",
				inputs: [{ ...input("chapter", 2), type: "memories", link: "incompatible" }],
				outputs: [],
				warning: "wrong type",
			},
		],
		ends: [{ ...chapter, source: 2 }],
		addable: [],
	};
	const drawing = layout(check);
	expect(drawing.ports).toContainEqual(expect.objectContaining({ row: 1, drops: true }));
	expect(drawing.segments).toMatchObject([
		{ row: 1, source: 0 },
		{ row: 3, source: 2, link: "incompatible" },
		{ kind: "end", source: 2 },
	]);
});
