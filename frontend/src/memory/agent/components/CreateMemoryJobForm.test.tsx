import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import {
	addMemoryJobMemoryAgentJobsPost,
	readMemoryAgentConfigMemoryAgentConfigGet,
} from "@/api/endpoints/default/default";
import type { MemoryAgentConfig, MemoryAgentToolsetOption } from "@/api/models";
import { CreateMemoryJobForm } from "./CreateMemoryJobForm";

vi.mock("@/api/endpoints/default/default", async (importOriginal) => {
	const original = await importOriginal<typeof import("@/api/endpoints/default/default")>();
	return {
		...original,
		addMemoryJobMemoryAgentJobsPost: vi.fn(),
		readMemoryAgentConfigMemoryAgentConfigGet: vi.fn(),
	};
});

class ResizeObserverMock implements ResizeObserver {
	disconnect() {}
	observe() {}
	unobserve() {}
}

beforeAll(() => {
	globalThis.ResizeObserver = ResizeObserverMock;
});

function toolset(
	name: string,
	options: Partial<MemoryAgentToolsetOption> = {},
): MemoryAgentToolsetOption {
	return {
		configSchema: {
			additionalProperties: false,
			properties: {},
			type: "object",
		},
		defaultEnabled: false,
		description: `${name} description`,
		excludes: [],
		kind: "memory",
		label: name,
		name,
		requires: [],
		...options,
	};
}

const config: MemoryAgentConfig = {
	models: [
		{
			description: "No thinking",
			label: "Test model",
			name: "deepseek:deepseek-v4-flash-none",
		},
	],
	toolsets: [
		toolset("legacy", { defaultEnabled: true, excludes: ["reader"] }),
		toolset("reader", { excludes: ["legacy"] }),
		toolset("writer", {
			configSchema: {
				additionalProperties: false,
				properties: {
					retention: {
						minimum: 1,
						title: "Retention",
						type: "integer",
					},
				},
				required: ["retention"],
				type: "object",
			},
			requires: ["reader"],
		}),
	],
};

beforeEach(() => {
	vi.clearAllMocks();
	vi.mocked(readMemoryAgentConfigMemoryAgentConfigGet).mockResolvedValue({
		data: config,
		headers: new Headers(),
		status: 200,
	});
	vi.mocked(addMemoryJobMemoryAgentJobsPost).mockResolvedValue({
		data: {
			claimExpiresAt: null,
			createdAt: "2026-09-03T00:00:00Z",
			jobParams: {
				version: 3,
				stages: [
					{
						stageName: "record_memories",
						modelName: "deepseek:deepseek-v4-flash-none",
						toolsets: { reader: {}, writer: { retention: 4 } },
					},
				],
			},
			memoryGroupId: "group-1",
			memoryJobId: "job-1",
			updatedAt: "2026-09-03T00:00:00Z",
		},
		headers: new Headers(),
		status: 201,
	});
});

it("shows catalog request failures instead of reading them as configuration", async () => {
	vi.mocked(readMemoryAgentConfigMemoryAgentConfigGet).mockResolvedValueOnce({
		data: { detail: "Could not validate credentials" },
		headers: new Headers(),
		status: 401,
	});

	render(
		<CreateMemoryJobForm memoryGroupId="group-1" onCreated={vi.fn()} closeDialog={vi.fn()} />,
	);

	expect(await screen.findByText("Could not validate credentials")).toBeVisible();
	expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
});

it("uses catalog defaults and submits dependencies with schema-driven configuration", async () => {
	const onCreated = vi.fn().mockResolvedValue(undefined);
	render(
		<CreateMemoryJobForm memoryGroupId="group-1" onCreated={onCreated} closeDialog={vi.fn()} />,
	);

	fireEvent.click(await screen.findByRole("button", { name: "Toolsets (1 selected)" }));
	expect(screen.getByRole("checkbox", { name: "legacy" })).toBeChecked();
	const writer = screen.getByRole("checkbox", { name: "writer" });
	fireEvent.click(writer);

	expect(writer).toBeChecked();
	expect(screen.getByRole("checkbox", { name: "reader" })).toBeChecked();
	expect(screen.getByRole("checkbox", { name: "legacy" })).not.toBeChecked();

	fireEvent.click(screen.getByRole("button", { name: "Configure writer" }));
	const retention = await screen.findByRole("spinbutton");
	fireEvent.change(retention, { target: { value: "4" } });
	await waitFor(() =>
		expect(screen.getByRole("button", { name: "Save configuration" })).toBeEnabled(),
	);
	fireEvent.click(screen.getByRole("button", { name: "Save configuration" }));
	fireEvent.click(screen.getByRole("button", { name: "Create job" }));

	await waitFor(() =>
		expect(addMemoryJobMemoryAgentJobsPost).toHaveBeenCalledWith({
			endChapterNum: null,
			memoryGroupId: "group-1",
			params: {
				version: 3,
				stages: [
					{
						stageName: "record_memories",
						modelName: "deepseek:deepseek-v4-flash-none",
						toolsets: { reader: {}, writer: { retention: 4 } },
					},
					{
						stageName: "translate_terms",
						modelName: "deepseek:deepseek-v4-flash-none",
						includeConventions: false,
					},
				],
			},
			startChapterNum: null,
		}),
	);
	expect(onCreated).toHaveBeenCalledWith("job-1");
});

it("can create a naming-only job that follows conventions without recording configuration", async () => {
	render(
		<CreateMemoryJobForm memoryGroupId="group-1" onCreated={vi.fn()} closeDialog={vi.fn()} />,
	);
	fireEvent.click(await screen.findByRole("checkbox", { name: "Record memories" }));
	fireEvent.click(screen.getByRole("checkbox", { name: "Follow naming conventions" }));
	expect(screen.queryByRole("checkbox", { name: "legacy" })).not.toBeInTheDocument();
	fireEvent.click(screen.getByRole("button", { name: "Create job" }));
	await waitFor(() =>
		expect(addMemoryJobMemoryAgentJobsPost).toHaveBeenCalledWith({
			memoryGroupId: "group-1",
			startChapterNum: null,
			endChapterNum: null,
			params: {
				version: 3,
				stages: [
					{
						stageName: "translate_terms",
						modelName: "deepseek:deepseek-v4-flash-none",
						includeConventions: true,
					},
				],
			},
		}),
	);
});

it("can create a conventions-only job with its own model", async () => {
	render(
		<CreateMemoryJobForm memoryGroupId="group-1" onCreated={vi.fn()} closeDialog={vi.fn()} />,
	);
	fireEvent.click(await screen.findByRole("checkbox", { name: "Record memories" }));
	fireEvent.click(screen.getByRole("checkbox", { name: "Translate glossary terms" }));
	expect(screen.queryByLabelText("Conventions model")).not.toBeInTheDocument();
	fireEvent.click(screen.getByRole("checkbox", { name: "Summarize naming conventions" }));
	expect(screen.getByLabelText("Conventions model")).toBeVisible();
	fireEvent.click(screen.getByRole("button", { name: "Create job" }));
	await waitFor(() =>
		expect(addMemoryJobMemoryAgentJobsPost).toHaveBeenCalledWith({
			memoryGroupId: "group-1",
			startChapterNum: null,
			endChapterNum: null,
			params: {
				version: 3,
				stages: [
					{
						stageName: "summarize_conventions",
						modelName: "deepseek:deepseek-v4-flash-none",
					},
				],
			},
		}),
	);
});

it("requires at least one stage", async () => {
	render(
		<CreateMemoryJobForm memoryGroupId="group-1" onCreated={vi.fn()} closeDialog={vi.fn()} />,
	);
	fireEvent.click(await screen.findByRole("checkbox", { name: "Record memories" }));
	fireEvent.click(screen.getByRole("checkbox", { name: "Translate glossary terms" }));
	fireEvent.click(screen.getByRole("button", { name: "Create job" }));
	expect(await screen.findByText("Select at least one stage.")).toBeVisible();
	expect(addMemoryJobMemoryAgentJobsPost).not.toHaveBeenCalled();
});
