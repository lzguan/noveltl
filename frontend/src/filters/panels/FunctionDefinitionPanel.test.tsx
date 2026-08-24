import { createFilterFunction, validateFilterFunction } from "@/api/endpoints/filters/filters";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FunctionDefinitionPanel } from "./FunctionDefinitionPanel";

vi.mock("@/api/endpoints/filters/filters", () => ({
	createFilterFunction: vi.fn(),
	validateFilterFunction: vi.fn(),
}));

describe("FunctionDefinitionPanel", () => {
	beforeEach(() => vi.clearAllMocks());

	it("validates and uploads the current form state", async () => {
		vi.mocked(validateFilterFunction).mockResolvedValue({
			status: 200,
			data: {
				signature: {
					args: [],
					output: { kind: "field", type: "string", mutable: false },
				},
			},
			headers: new Headers(),
		});
		vi.mocked(createFilterFunction).mockResolvedValue({
			status: 201,
			data: {
				createdAt: "2026-08-05T00:00:00Z",
				functionDefinition: { name: "literalString", value: "Alice" },
				functionDefinitionId: "function-1",
				functionName: "character-name",
				namespace: "glossary",
				updatedAt: "2026-08-05T00:00:00Z",
			},
			headers: new Headers(),
		});
		render(<FunctionDefinitionPanel />);

		fireEvent.change(screen.getByLabelText("Namespace"), {
			target: { value: " glossary " },
		});
		fireEvent.change(screen.getByLabelText("Name"), {
			target: { value: " character-name " },
		});
		fireEvent.change(screen.getByLabelText("Function definition"), {
			target: { value: '{"name":"literalString","value":"Alice"}' },
		});
		fireEvent.click(screen.getByRole("button", { name: "Validate" }));

		await screen.findByText("Function is valid");
		expect(validateFilterFunction).toHaveBeenCalledWith({
			functionDefinition: { name: "literalString", value: "Alice" },
		});

		fireEvent.click(screen.getByRole("button", { name: "Upload" }));
		await screen.findByText("Function uploaded");
		expect(createFilterFunction).toHaveBeenCalledWith({
			functionDefinition: { name: "literalString", value: "Alice" },
			functionName: "character-name",
			namespace: "glossary",
		});
	});

	it("reports invalid JSON without making a request", () => {
		render(<FunctionDefinitionPanel />);
		fireEvent.change(screen.getByLabelText("Function definition"), {
			target: { value: "[1, 2]" },
		});

		fireEvent.click(screen.getByRole("button", { name: "Validate" }));

		expect(screen.getByRole("alert")).toHaveTextContent(
			"Function definition must be a JSON object.",
		);
		expect(validateFilterFunction).not.toHaveBeenCalled();
	});

	it("disables the form while a request is pending", async () => {
		vi.mocked(validateFilterFunction).mockImplementation(() => new Promise(() => {}));
		render(<FunctionDefinitionPanel />);
		fireEvent.change(screen.getByLabelText("Function definition"), {
			target: { value: "{}" },
		});

		fireEvent.click(screen.getByRole("button", { name: "Validate" }));

		await waitFor(() =>
			expect(screen.getByRole("button", { name: "Validating…" })).toBeDisabled(),
		);
		expect(screen.getByLabelText("Namespace")).toBeDisabled();
		expect(screen.getByRole("button", { name: "Upload" })).toBeDisabled();
	});
});
