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
	it("orders model and chapters before collapsed advanced settings", () => {
		render(<CreateAutoLabelPanel onCreateRun={vi.fn()} />);

		const model = screen.getByRole("combobox", { name: "Model" });
		const start = screen.getByRole("textbox", { name: "Start chapter" });
		const advanced = screen.getByRole("button", { name: "Advanced Settings" });

		expect(
			model.compareDocumentPosition(start) & Node.DOCUMENT_POSITION_FOLLOWING,
		).toBeTruthy();
		expect(
			start.compareDocumentPosition(advanced) & Node.DOCUMENT_POSITION_FOLLOWING,
		).toBeTruthy();
		expect(advanced).toBeDisabled();
		expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();
	});

	it("submits generated defaults and the chapter range", async () => {
		const onCreateRun = vi.fn();
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
		render(<CreateAutoLabelPanel onCreateRun={vi.fn()} />);

		await selectModel("cluener");
		fireEvent.click(screen.getByRole("button", { name: "Advanced Settings" }));
		fireEvent.change(screen.getByRole("spinbutton", { name: "Chunk Size" }), {
			target: { value: "513" },
		});

		await waitFor(() => expect(screen.getByRole("button", { name: "Create" })).toBeDisabled());
	});

	it("creates models without advanced fields from their generated schema branch", async () => {
		const onCreateRun = vi.fn();
		render(<CreateAutoLabelPanel onCreateRun={onCreateRun} />);

		await selectModel("do_nothing");
		expect(screen.getByRole("button", { name: "Advanced Settings" })).toBeDisabled();
		fireEvent.click(screen.getByRole("button", { name: "Create" }));

		expect(onCreateRun).toHaveBeenCalledWith(
			{ modelName: "do_nothing" },
			{ start: undefined, end: undefined },
		);
	});
});
