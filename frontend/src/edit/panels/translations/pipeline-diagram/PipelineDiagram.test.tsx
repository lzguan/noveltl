import { render, screen } from "@testing-library/react";
import type { TranslationPipelineCheck } from "@/api/models";
import { PipelineDiagram } from "./PipelineDiagram";

it("renders backend port states, explicit segments, drops, and accessible warnings", () => {
	const check: TranslationPipelineCheck = {
		stages: [
			{
				action: "load_inputs",
				inputs: [],
				outputs: [{ stream: "chapter", type: "chapter" }],
				warning: null,
			},
			{
				action: "prune_memories",
				inputs: [
					{
						stream: "chapter",
						type: "memories",
						sourceType: "chapter",
						source: 0,
						link: "incompatible",
						optional: false,
						drops: true,
					},
					{
						stream: "memories",
						type: "memories",
						sourceType: null,
						source: null,
						link: "broken",
						optional: false,
						drops: false,
					},
					{
						stream: "context",
						type: "memories",
						sourceType: null,
						source: null,
						link: "absent",
						optional: true,
						drops: false,
					},
				],
				outputs: [],
				warning: "requires memories",
			},
			{
				action: "translate",
				inputs: [
					{
						stream: "chapter",
						type: "chapter",
						sourceType: "chapter",
						source: 0,
						link: "linked",
						optional: false,
						drops: false,
					},
				],
				outputs: [{ stream: "chapter", type: "chapter" }],
				warning: null,
			},
		],
		ends: [{ stream: "chapter", type: "chapter", source: 2 }],
		addable: [],
	};
	const { container } = render(<PipelineDiagram check={check} />);
	expect(screen.getByRole("img")).toHaveAccessibleName(
		"Translation pipeline: Load inputs → prune memories (warning: requires memories) → translate",
	);
	expect(
		container.querySelector(
			'circle[data-stream="chapter"][data-stage="0"][data-link="output"]',
		),
	).toBeInTheDocument();
	expect(
		container.querySelector(
			'circle[data-stream="chapter"][data-stage="1"][data-link="incompatible"]',
		),
	).toHaveClass("text-destructive");
	expect(
		container.querySelector(
			'line[data-stream="chapter"][data-stage="1"][data-link="incompatible"]',
		),
	).toHaveAttribute("data-source", "0");
	expect(
		container.querySelector('path[data-stream="memories"][data-stage="1"][data-link="broken"]'),
	).toBeInTheDocument();
	expect(
		container.querySelector('circle[data-stream="memories"][data-link="broken"]'),
	).toHaveClass("text-destructive");
	expect(
		container.querySelector('circle[data-stream="context"][data-link="absent"]'),
	).toHaveClass("text-muted-foreground", "fill-background");
	expect(container.querySelector('line[data-stream="context"]')).not.toBeInTheDocument();
	expect(container.querySelector('line[data-stream="memories"]')).not.toBeInTheDocument();
	expect(container.querySelector('line[data-stage="2"][data-link="linked"]')).toHaveAttribute(
		"data-source",
		"0",
	);
	expect(container.querySelector('line[data-link="end"]')).toHaveAttribute("data-source", "2");
	expect(container.querySelector("rect[stroke-dasharray] title")).toHaveTextContent(
		"requires memories",
	);
	expect(screen.getByText(/ends here/)).toBeInTheDocument();
	expect(
		container.querySelector('text[data-stream="chapter"][data-stage="1"][data-port="input"]'),
	).toHaveTextContent("memories");
});

it("labels changed output and input types beside their ports without repeating the header type", () => {
	const check: TranslationPipelineCheck = {
		stages: [
			{
				action: "load_inputs",
				inputs: [],
				outputs: [{ stream: "chapter", type: "chapter" }],
				warning: null,
			},
			{
				action: "transform",
				inputs: [],
				outputs: [{ stream: "chapter", type: "memories" }],
				warning: null,
			},
			{
				action: "consume",
				inputs: [
					{
						stream: "chapter",
						type: "memories",
						sourceType: "memories",
						source: 1,
						link: "linked",
						optional: false,
						drops: true,
					},
				],
				outputs: [],
				warning: null,
			},
		],
		ends: [],
		addable: [],
	};
	const { container } = render(<PipelineDiagram check={check} />);
	expect(container.querySelector('text[data-stage="0"][data-port="output"]')).toBeNull();
	expect(container.querySelector('text[data-stage="1"][data-port="output"]')).toHaveTextContent(
		"memories",
	);
	expect(container.querySelector('text[data-stage="2"][data-port="input"]')).toHaveTextContent(
		"memories",
	);
});
