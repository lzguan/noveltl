import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FunctionSignatureDisplay } from "./FunctionSignatureDisplay";

describe("FunctionSignatureDisplay", () => {
	it("displays object arguments and output as separate field tables", () => {
		render(
			<FunctionSignatureDisplay
				signature={{
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
				}}
			/>,
		);

		const inputTable = screen.getByRole("table", { name: "Argument 1 fields" });
		const outputTable = screen.getByRole("table", { name: "Return value fields" });

		expect(within(inputTable).getByText("label")).toBeInTheDocument();
		expect(within(inputTable).getByText("labelRef")).toBeInTheDocument();
		expect(within(outputTable).getByText("range")).toBeInTheDocument();
		expect(within(outputTable).getByText("textSpan")).toBeInTheDocument();
		expect(within(outputTable).getByText("word")).toBeInTheDocument();
		expect(within(outputTable).getByText("string")).toBeInTheDocument();
		expect(within(outputTable).getByText("score")).toBeInTheDocument();
		expect(within(outputTable).getByText("float")).toBeInTheDocument();
	});

	it("displays elementary types in compact cards", () => {
		render(
			<FunctionSignatureDisplay
				signature={{
					args: [{ kind: "field", type: "string", mutable: true }],
					output: { kind: "field", type: "bool", mutable: false },
				}}
			/>,
		);

		expect(screen.getByText("Argument 1")).toBeInTheDocument();
		expect(screen.getByText("string")).toBeInTheDocument();
		expect(screen.getByText("Mutable")).toBeInTheDocument();
		expect(screen.getByText("Return value")).toBeInTheDocument();
		expect(screen.getByText("bool")).toBeInTheDocument();
		expect(screen.queryByRole("table")).not.toBeInTheDocument();
	});

	it("identifies functions without arguments", () => {
		render(
			<FunctionSignatureDisplay
				signature={{ output: { kind: "field", type: "bool", mutable: false } }}
			/>,
		);

		expect(screen.getByText("No arguments")).toBeInTheDocument();
	});
});
