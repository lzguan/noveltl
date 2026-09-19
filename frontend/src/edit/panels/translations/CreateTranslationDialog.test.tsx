import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { MemoryGroupsProvider } from "@/memory/context/MemoryGroupsContext";
import { TranslationsPanel } from "./TranslationsPanel";

// Keep forms, schema validation, context, and generated clients real. Replace HTTP:
// creation must preserve dynamic config and drafts without touching a real database.
const schema = {
	type: "object",
	additionalProperties: false,
	required: ["model"],
	$defs: {
		ModelName: { type: "string", enum: ["qwen-plus", "qwen-flash"] },
		PluginName: { type: "string", enum: ["glossary", "continuity"] },
		MemoryType: { type: "string", enum: ["fact", "event"] },
	},
	properties: {
		model: { $ref: "#/$defs/ModelName", title: "Model", "x-ui": { control: "select" } },
		targetLanguage: {
			type: "string",
			default: "English",
			title: "Target language",
			"x-ui": { control: "text", showAfter: "model" },
			minLength: 1,
		},
		instructions: {
			type: "string",
			default: "",
			title: "Instructions",
			"x-ui": { control: "textarea", showAfter: "model" },
		},
		temperature: {
			title: "Temperature",
			"x-ui": { control: "number", showAfter: "model", placeholder: "Provider default" },
			anyOf: [{ type: "number", minimum: 0 }, { type: "null" }],
			default: null,
		},
		maxOutputTokens: {
			title: "Max output tokens",
			"x-ui": { control: "number", showAfter: "model", placeholder: "Provider default" },
			anyOf: [{ type: "integer", exclusiveMinimum: 0 }, { type: "null" }],
			default: null,
		},
		memoryGroupId: {
			title: "Memory group",
			"x-ui": {
				control: "resource-picker",
				resource: "memory-group",
				scope: "current-novel",
				placement: "job-inputs",
				stageScope: "first",
			},
			anyOf: [{ type: "string", format: "uuid" }, { type: "null" }],
			default: null,
		},
		excludeCurrentChapter: {
			type: "boolean",
			default: true,
			"x-ui": { control: "checkbox", stageScope: "first", showAfter: "model" },
		},
		pluginNames: {
			title: "Plugin names",
			"x-ui": {
				control: "filter-checklist",
				stageScope: "first",
				showAfter: "model",
				nullLabel: "All plugin names",
				emptyLabel: "Selecting none excludes all memories.",
			},
			anyOf: [{ type: "array", items: { $ref: "#/$defs/PluginName" } }, { type: "null" }],
			default: null,
		},
		memoryTypes: {
			title: "Memory types",
			"x-ui": {
				control: "filter-checklist",
				stageScope: "first",
				showAfter: "model",
				nullLabel: "All memory types",
				emptyLabel: "Selecting none excludes all memories.",
			},
			anyOf: [{ type: "array", items: { $ref: "#/$defs/MemoryType" } }, { type: "null" }],
			default: null,
		},
	},
};
const catalog = {
	actions: [
		{
			name: "dynamic-translation",
			label: "Translate with memories",
			inputTypes: ["chapter", "memories"],
			outputTypes: ["chapter"],
			allowedAsFirstStage: true,
			configSchema: schema,
		},
		{
			name: "plain",
			label: "Translate",
			inputTypes: ["chapter"],
			outputTypes: ["chapter"],
			allowedAsFirstStage: true,
			configSchema: schema,
		},
	],
};
beforeEach(() => {
	Object.defineProperties(HTMLElement.prototype, {
		hasPointerCapture: { configurable: true, value: () => false },
		releasePointerCapture: { configurable: true, value: () => undefined },
		setPointerCapture: { configurable: true, value: () => undefined },
		scrollIntoView: { configurable: true, value: () => undefined },
	});
	// JSDOM has no layout observer; only the schema form's checkbox needs this API.
	vi.stubGlobal(
		"ResizeObserver",
		class {
			observe() {}
			unobserve() {}
			disconnect() {}
		},
	);
});
function setup({
	reject = false,
	metadataFails = false,
	detailsFail = false,
	createWait,
}: {
	reject?: boolean;
	metadataFails?: boolean;
	detailsFail?: boolean;
	createWait?: Promise<void>;
} = {}) {
	const payloads: unknown[] = [];
	let metadataCalls = 0;
	vi.stubGlobal(
		"fetch",
		vi.fn(async (url: string, options?: RequestInit) => {
			if (url.includes("memory-groups"))
				return Response.json([
					{
						memoryGroupId: "group-1",
						memoryGroupName: "Real glossary",
						memoryLanguage: "en",
						novelId: "novel-1",
					},
				]);
			if (url.endsWith("/actions")) {
				metadataCalls++;
				return metadataFails && metadataCalls === 1
					? Response.json({ detail: "Metadata unavailable" }, { status: 503 })
					: Response.json(catalog);
			}
			if (options?.method === "POST") {
				if (typeof options.body === "string") payloads.push(JSON.parse(options.body));
				await createWait;
				if (reject && payloads.length === 1)
					return Response.json(
						{
							detail: [
								{
									loc: ["body", "stages", 0, "config", "instructions"],
									msg: "Please revise instructions",
								},
							],
						},
						{ status: 422 },
					);
				return Response.json({ jobId: "created-1" }, { status: 201 });
			}
			if (url.includes("/created-1/batches"))
				return detailsFail
					? Response.json({ detail: "Read failed" }, { status: 503 })
					: Response.json({
							job: {
								jobId: "created-1",
								config: {},
								stages: [],
								progress: {
									totalTasks: 1,
									completedTasks: 0,
									totalBatches: 1,
									startableBatches: 1,
								},
							},
							items: [],
							total: 0,
							observedAt: "2026-09-18T00:00:00Z",
						});
			if (url.includes("/translation-jobs?")) return Response.json({ items: [], total: 0 });
			throw new Error(`Unexpected request: ${url}`);
		}),
	);
	render(
		<MemoryGroupsProvider novelId="novel-1">
			<TranslationsPanel novelId="novel-1" chapterNumbers={[3, 5, 8]} />
		</MemoryGroupsProvider>,
	);
	fireEvent.click(screen.getByRole("button", { name: "+ Create job" }));
	return payloads;
}
afterEach(() => vi.unstubAllGlobals());
async function configure() {
	await screen.findByRole("option", { name: "Real glossary" });
	fireEvent.change(screen.getByLabelText("Memory group"), { target: { value: "group-1" } });
	fireEvent.change(screen.getByLabelText("Add stage"), {
		target: { value: "dynamic-translation" },
	});
	fireEvent.click(screen.getByRole("button", { name: "Add stage" }));
	fireEvent.change(screen.getByRole("combobox", { name: /Model/ }), { target: { value: "0" } });
	expect(screen.queryByLabelText(/Memory Group Id/i)).not.toBeInTheDocument();
	fireEvent.change(screen.getByLabelText(/Target language/), { target: { value: "French" } });
	fireEvent.change(screen.getByLabelText("Instructions"), {
		target: { value: "Keep names consistent" },
	});
	fireEvent.submit(screen.getByRole("button", { name: "Save configuration" }).closest("form")!);
}
it("submits runtime action names, inclusive bounds, and the selected memory group", async () => {
	const payloads = setup();
	await configure();
	expect(screen.getByLabelText("From chapter")).toHaveValue(3);
	expect(screen.getByLabelText("To chapter (inclusive)")).toHaveValue(8);
	fireEvent.click(screen.getByRole("button", { name: "Create job" }));
	await screen.findByRole("dialog", { name: /Job created-.*Batches/ });
	expect(payloads).toEqual([
		{
			novelId: "novel-1",
			config: { startChapterNum: 3, endChapterNum: 9, batchSize: 100 },
			stages: [
				{
					action: "dynamic-translation",
					config: {
						model: "qwen-plus",
						targetLanguage: "French",
						instructions: "Keep names consistent",
						excludeCurrentChapter: true,
						temperature: null,
						maxOutputTokens: null,
						pluginNames: null,
						memoryTypes: null,
						memoryGroupId: "group-1",
					},
				},
			],
		},
	]);
	// Creation opens the viewer, but does not send a Start request.
	expect(payloads).toHaveLength(1);
});
it("retains configuration after server rejection and shows its stage error", async () => {
	const payloads = setup({ reject: true });
	await configure();
	fireEvent.click(screen.getByRole("button", { name: "Create job" }));
	await screen.findAllByText(/Please revise instructions/);
	expect(screen.getByText("qwen-plus · French · Custom instructions")).toBeInTheDocument();
	expect(screen.getByRole("dialog")).toBeInTheDocument();
	fireEvent.click(screen.getByRole("button", { name: "Create job" }));
	await screen.findByRole("dialog", { name: /Job created-.*Batches/ });
	expect(payloads).toHaveLength(2);
	expect(payloads[0]).toEqual(payloads[1]);
});
it("retries metadata loading and retains a created job ID when detail loading fails", async () => {
	const payloads = setup({ metadataFails: true, detailsFail: true });
	await screen.findByText("Metadata unavailable");
	fireEvent.click(screen.getByRole("button", { name: "Retry loading" }));
	await configure();
	fireEvent.click(screen.getByRole("button", { name: "Create job" }));
	await screen.findByText("Read failed");
	expect(screen.getByText("created-1")).toBeInTheDocument();
	fireEvent.click(screen.getByRole("button", { name: "Reload details" }));
	await waitFor(() =>
		expect(screen.getByRole("button", { name: "Reload details" })).toBeEnabled(),
	);
	expect(payloads).toHaveLength(1);
});
it("removes the dependent suffix when the initial memory group is removed", async () => {
	setup();
	await configure();
	fireEvent.change(screen.getByLabelText("Memory group"), { target: { value: "" } });
	fireEvent.click(screen.getByRole("button", { name: "Remove stages" }));
	expect(screen.getByRole("button", { name: "Create job" })).toBeDisabled();
	expect(
		screen.queryByRole("option", { name: "Translate with memories" }),
	).not.toBeInTheDocument();
});

it("prevents duplicate submission while creation is pending", async () => {
	let finishCreation = () => {};
	const creation = new Promise<void>((resolve) => {
		finishCreation = resolve;
	});
	const payloads = setup({ createWait: creation });
	await configure();
	fireEvent.click(screen.getByRole("button", { name: "Create job" }));
	const pendingButton = screen.getByRole("button", { name: "Creating…" });
	expect(pendingButton).toBeDisabled();
	fireEvent.click(pendingButton);
	expect(payloads).toHaveLength(1);
	finishCreation();
	await screen.findByRole("dialog", { name: /Job created-.*Batches/ });
});

it("renders nullable numbers as labeled inputs and preserves numeric values and clearing", async () => {
	const payloads = setup();
	await configure();
	fireEvent.click(screen.getByRole("button", { name: "Configure" }));
	const temperature = screen.getByRole("spinbutton", { name: "Temperature" });
	const tokens = screen.getByRole("spinbutton", { name: "Max output tokens" });
	expect(temperature).toHaveValue(null);
	expect(tokens).toHaveValue(null);
	expect(
		screen.queryByRole("combobox", { name: /Temperature|Max output tokens/ }),
	).not.toBeInTheDocument();
	fireEvent.change(temperature, { target: { value: "0" } });
	fireEvent.change(tokens, { target: { value: "2048" } });
	fireEvent.submit(screen.getByRole("button", { name: "Save configuration" }).closest("form")!);
	fireEvent.click(screen.getByRole("button", { name: "Configure" }));
	expect(screen.getByRole("spinbutton", { name: "Temperature" })).toHaveValue(0);
	expect(screen.getByRole("spinbutton", { name: "Max output tokens" })).toHaveValue(2048);
	fireEvent.change(screen.getByRole("spinbutton", { name: "Max output tokens" }), {
		target: { value: "" },
	});
	fireEvent.submit(screen.getByRole("button", { name: "Save configuration" }).closest("form")!);
	fireEvent.click(screen.getByRole("button", { name: "Create job" }));
	await screen.findByRole("dialog", { name: /Job created-.*Batches/ });
	expect(payloads[0]).toMatchObject({ stages: [{ config: { temperature: 0 } }] });
	expect(JSON.stringify(payloads[0])).not.toContain('"maxOutputTokens":2048');
});

it("waits for a model and renders nullable filters with explicit all and selected semantics", async () => {
	const payloads = setup();
	await screen.findByRole("option", { name: "Real glossary" });
	fireEvent.change(screen.getByLabelText("Memory group"), { target: { value: "group-1" } });
	fireEvent.change(screen.getByLabelText("Add stage"), {
		target: { value: "dynamic-translation" },
	});
	fireEvent.click(screen.getByRole("button", { name: "Add stage" }));
	expect(screen.getByRole("combobox", { name: /Model/ })).toBeInTheDocument();
	expect(screen.queryByLabelText("Instructions")).not.toBeInTheDocument();
	expect(screen.queryByRole("spinbutton", { name: "Temperature" })).not.toBeInTheDocument();
	expect(screen.queryByLabelText("All plugin names")).not.toBeInTheDocument();
	expect(screen.getByRole("button", { name: "Save configuration" })).toBeDisabled();
	fireEvent.change(screen.getByRole("combobox", { name: /Model/ }), { target: { value: "0" } });
	expect(screen.getByLabelText("Instructions")).toBeInTheDocument();
	expect(screen.getByLabelText("All plugin names")).toBeChecked();
	expect(screen.getByLabelText("All memory types")).toBeChecked();
	expect(screen.queryByText(/option [12]/i)).not.toBeInTheDocument();
	fireEvent.click(screen.getByLabelText("All plugin names"));
	fireEvent.click(screen.getByLabelText("glossary"));
	fireEvent.click(screen.getByLabelText("All memory types"));
	// Explicit [] is intentionally distinct from unrestricted null.
	fireEvent.submit(screen.getByRole("button", { name: "Save configuration" }).closest("form")!);
	fireEvent.click(screen.getByRole("button", { name: "Configure" }));
	expect(screen.getByLabelText("glossary")).toBeChecked();
	expect(screen.getByLabelText("All memory types")).not.toBeChecked();
	fireEvent.change(screen.getByRole("combobox", { name: /Model/ }), { target: { value: "-1" } });
	expect(screen.queryByLabelText("Instructions")).not.toBeInTheDocument();
	fireEvent.change(screen.getByRole("combobox", { name: /Model/ }), { target: { value: "1" } });
	expect(screen.getByLabelText("glossary")).toBeChecked();
	fireEvent.submit(screen.getByRole("button", { name: "Save configuration" }).closest("form")!);
	fireEvent.click(screen.getByRole("button", { name: "Create job" }));
	await screen.findByRole("dialog", { name: /Job created-.*Batches/ });
	expect(payloads[0]).toMatchObject({
		stages: [{ config: { model: "qwen-flash", pluginNames: ["glossary"], memoryTypes: [] } }],
	});
}, 20000);
