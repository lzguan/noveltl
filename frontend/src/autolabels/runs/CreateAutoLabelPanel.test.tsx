import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CreateAutoLabelPanel } from "./CreateAutoLabelPanel";

beforeAll(() => {
	Object.defineProperties(HTMLElement.prototype, {
		hasPointerCapture: { configurable: true, value: () => false },
		releasePointerCapture: { configurable: true, value: () => undefined },
		scrollIntoView: { configurable: true, value: () => undefined },
		setPointerCapture: { configurable: true, value: () => undefined },
	});
});

async function selectModel(modelName: "cluener" | "do_nothing") {
	const trigger = screen.getByRole("combobox", { name: "Model" });
	fireEvent.pointerDown(trigger, { button: 0, ctrlKey: false, pointerType: "mouse" });
	fireEvent.click(await screen.findByRole("option", { name: modelName }));
}

describe("CreateAutoLabelPanel", () => {
	it("disables creation until a model is selected", () => {
		render(<CreateAutoLabelPanel onCreateRun={vi.fn(() => null)} />);

		expect(screen.getByRole("button", { name: "Advanced Settings" })).toBeDisabled();
		expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();
	});

	it("submits generated defaults and the chapter range", async () => {
		const onCreateRun = vi.fn(async () => null);
		render(<CreateAutoLabelPanel onCreateRun={onCreateRun} />);

		await selectModel("cluener");
		fireEvent.change(screen.getByRole("textbox", { name: "Start chapter" }), {
			target: { value: "2" },
		});
		fireEvent.change(screen.getByRole("textbox", { name: "End chapter" }), {
			target: { value: "8" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Create" }));

		expect(onCreateRun).toHaveBeenCalledWith(
			expect.objectContaining({
				modelName: "cluener",
				chunkSize: 500,
				forceChunk: false,
				separators: expect.objectContaining({ "\n": 1, "!": 2, ",": 3 }),
			}),
			{ start: 2, end: 8 },
		);
		await waitFor(() =>
			expect(screen.getByRole("combobox", { name: "Model" })).toHaveTextContent(
				"Select a model...",
			),
		);
	});

	it("disables creation while advanced parameters are invalid", async () => {
		render(<CreateAutoLabelPanel onCreateRun={vi.fn(() => null)} />);

		await selectModel("cluener");
		fireEvent.click(screen.getByRole("button", { name: "Advanced Settings" }));
		fireEvent.change(screen.getByRole("spinbutton", { name: "Chunk Size" }), {
			target: { value: "513" },
		});

		await waitFor(() => expect(screen.getByRole("button", { name: "Create" })).toBeDisabled());
	});

	it("creates models without advanced fields from their generated schema branch", async () => {
		const onCreateRun = vi.fn(async () => null);
		render(<CreateAutoLabelPanel onCreateRun={onCreateRun} />);

		await selectModel("do_nothing");
		expect(screen.getByRole("button", { name: "Advanced Settings" })).toBeDisabled();
		fireEvent.click(screen.getByRole("button", { name: "Create" }));

		expect(onCreateRun).toHaveBeenCalledWith(
			{ modelName: "do_nothing" },
			{ start: undefined, end: undefined },
		);
	});

	it("keeps form inputs and displays an alert when creation fails", async () => {
		const onCreateRun = vi.fn(async () => "Could not start the autolabel run.");
		render(<CreateAutoLabelPanel onCreateRun={onCreateRun} />);

		await selectModel("do_nothing");
		fireEvent.change(screen.getByRole("textbox", { name: "Start chapter" }), {
			target: { value: "3" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Create" }));

		expect(await screen.findByRole("alert")).toHaveTextContent(
			"Could not start the autolabel run.",
		);
		expect(screen.getByRole("textbox", { name: "Start chapter" })).toHaveValue("3");
		expect(screen.getByRole("combobox", { name: "Model" })).toHaveTextContent("do_nothing");
	});
});
