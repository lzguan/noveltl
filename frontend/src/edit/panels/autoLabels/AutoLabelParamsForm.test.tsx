import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import {
	AutoLabelParamsForm,
	type AutoLabelParams,
	autoLabelParamModels,
	createAutoLabelParams,
} from "./AutoLabelParamsForm";

beforeAll(() => {
	Object.defineProperties(HTMLElement.prototype, {
		hasPointerCapture: { configurable: true, value: () => false },
		releasePointerCapture: { configurable: true, value: () => undefined },
		scrollIntoView: { configurable: true, value: () => undefined },
		setPointerCapture: { configurable: true, value: () => undefined },
	});
});

function Harness({
	onChange = vi.fn(),
	onValidityChange = vi.fn(),
}: {
	onChange?: (value: AutoLabelParams) => void;
	onValidityChange?: (valid: boolean) => void;
}) {
	const model = autoLabelParamModels.find((candidate) => candidate.name === "cluener");
	if (!model) throw new Error("Expected the generated params schema to include cluener");

	const [value, setValue] = useState(() => createAutoLabelParams(model.name));

	return (
		<AutoLabelParamsForm
			model={model}
			value={value}
			onChange={(next) => {
				setValue(next);
				onChange(next);
			}}
			onValidityChange={onValidityChange}
		/>
	);
}

describe("AutoLabelParamsForm", () => {
	it("renders generated defaults with the backend priority semantics", () => {
		render(<Harness />);

		expect(screen.getByRole("spinbutton", { name: "Chunk Size" })).toHaveValue(500);
		expect(screen.getByRole("checkbox", { name: "Force Chunk" })).not.toBeChecked();
		expect(screen.getAllByLabelText(/^Separator \d+$/)).toHaveLength(13);
		expect(screen.getByLabelText("Separator 1")).toHaveValue("\\n");
		expect(
			screen.getByRole("combobox", { name: "Priority for separator \\n" }),
		).toHaveTextContent("HIGH");
		expect(screen.queryByText(/Pydantic schema for a Cluener model/i)).not.toBeInTheDocument();
	});

	it("reports schema constraint failures", async () => {
		const onValidityChange = vi.fn();
		render(<Harness onValidityChange={onValidityChange} />);

		fireEvent.change(screen.getByRole("spinbutton", { name: "Chunk Size" }), {
			target: { value: "513" },
		});

		await waitFor(() => expect(onValidityChange).toHaveBeenLastCalledWith(false));
		expect(screen.getByText(/must be <= 512/i)).toBeVisible();
	});

	it("supports adding and removing separators while rejecting invalid keys", async () => {
		const onChange = vi.fn();
		const onValidityChange = vi.fn();
		render(<Harness onChange={onChange} onValidityChange={onValidityChange} />);

		fireEvent.click(screen.getByRole("button", { name: "Add separator" }));
		expect(screen.getByText("Enter exactly one character.")).toBeVisible();
		expect(onValidityChange).toHaveBeenLastCalledWith(false);

		fireEvent.change(screen.getByLabelText("Separator 14"), {
			target: { value: "|" },
		});
		await waitFor(() => expect(onValidityChange).toHaveBeenLastCalledWith(true));
		expect(onChange).toHaveBeenLastCalledWith(
			expect.objectContaining({
				separators: expect.objectContaining({ "|": 3 }),
			}),
		);

		fireEvent.click(screen.getByRole("button", { name: "Remove separator |" }));
		expect(screen.queryByLabelText("Separator 14")).not.toBeInTheDocument();
	});

	it("rejects duplicate separator characters without overwriting the stored map", () => {
		const onChange = vi.fn();
		const onValidityChange = vi.fn();
		render(<Harness onChange={onChange} onValidityChange={onValidityChange} />);

		fireEvent.change(screen.getByLabelText("Separator 1"), {
			target: { value: "!" },
		});

		expect(screen.getAllByText("Separator characters must be unique.")).toHaveLength(2);
		expect(onValidityChange).toHaveBeenLastCalledWith(false);
		expect(onChange).not.toHaveBeenCalled();
	});
});
