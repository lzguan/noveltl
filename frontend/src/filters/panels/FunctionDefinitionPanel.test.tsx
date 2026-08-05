import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { FunctionDefinitionFormModel } from "../types";
import { FunctionDefinitionPanel } from "./FunctionDefinitionPanel";

function makeFormModel(
	overrides: Partial<FunctionDefinitionFormModel> = {},
): FunctionDefinitionFormModel {
	return {
		functionNamespace: "glossary",
		functionName: "character-name",
		functionDefinitionText: '{"name":"literalString","value":"Alice"}',
		functionDefinitionError: null,
		formStatus: { status: "idle" },
		setFunctionNamespace: vi.fn(),
		setFunctionName: vi.fn(),
		setFunctionDefinitionText: vi.fn(),
		validateFunctionDefinition: vi.fn(async () => {}),
		uploadFunctionDefinition: vi.fn(async () => {}),
		...overrides,
	};
}

describe("FunctionDefinitionPanel", () => {
	it("connects each field and action to its semantic command", () => {
		const model = makeFormModel();
		render(<FunctionDefinitionPanel {...model} />);

		fireEvent.change(screen.getByLabelText("Namespace"), { target: { value: "chapter" } });
		fireEvent.change(screen.getByLabelText("Name"), { target: { value: "speaker" } });
		fireEvent.change(screen.getByLabelText("Function definition"), {
			target: { value: '{"name":"get","fieldName":"speaker"}' },
		});
		fireEvent.click(screen.getByRole("button", { name: "Validate" }));
		fireEvent.click(screen.getByRole("button", { name: "Upload" }));

		expect(model.setFunctionNamespace).toHaveBeenCalledWith("chapter");
		expect(model.setFunctionName).toHaveBeenCalledWith("speaker");
		expect(model.setFunctionDefinitionText).toHaveBeenCalledWith(
			'{"name":"get","fieldName":"speaker"}',
		);
		expect(model.validateFunctionDefinition).toHaveBeenCalledOnce();
		expect(model.uploadFunctionDefinition).toHaveBeenCalledOnce();
	});

	it("shows local editor errors and a validated signature", () => {
		const { rerender } = render(
			<FunctionDefinitionPanel
				{...makeFormModel({ functionDefinitionError: "Unexpected end of JSON input" })}
			/>,
		);

		expect(screen.getByRole("alert")).toHaveTextContent("Unexpected end of JSON input");

		rerender(
			<FunctionDefinitionPanel
				{...makeFormModel({
					formStatus: {
						status: "validated",
						signature: {
							args: [
								{
									kind: "schema",
									fields: {
										label: { kind: "field", type: "labelRef", mutable: false },
									},
								},
							],
							output: {
								kind: "schema",
								fields: {
									range: { kind: "field", type: "textSpan", mutable: false },
									word: { kind: "field", type: "string", mutable: false },
									score: { kind: "field", type: "float", mutable: false },
								},
							},
						},
					},
				})}
			/>,
		);

		expect(screen.getByText("Function is valid")).toBeInTheDocument();
		expect(screen.getByRole("table", { name: "Argument 1 fields" })).toBeInTheDocument();
		expect(screen.getByRole("table", { name: "Return value fields" })).toBeInTheDocument();
	});

	it("disables the editor and identifies the active request", () => {
		render(
			<FunctionDefinitionPanel {...makeFormModel({ formStatus: { status: "uploading" } })} />,
		);

		expect(screen.getByLabelText("Namespace")).toBeDisabled();
		expect(screen.getByRole("button", { name: "Uploading…" })).toBeDisabled();
		expect(screen.getByRole("button", { name: "Validate" })).toBeDisabled();
	});
});
