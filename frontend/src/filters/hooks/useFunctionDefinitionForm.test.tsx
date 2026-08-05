import { createFilterFunction, validateFilterFunction } from "@/api/endpoints/filters/filters";
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiErrorMessage } from "../apiErrors";
import {
	parseFunctionDefinitionText,
	useFunctionDefinitionForm,
} from "./useFunctionDefinitionForm";

vi.mock("@/api/endpoints/filters/filters", () => ({
	createFilterFunction: vi.fn(),
	validateFilterFunction: vi.fn(),
}));

describe("useFunctionDefinitionForm", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("formats both FastAPI validation arrays and string error details", () => {
		expect(apiErrorMessage({ detail: "Not authenticated." }, "Fallback")).toBe(
			"Not authenticated.",
		);
		expect(
			apiErrorMessage(
				{
					detail: [
						{
							loc: ["body", "functionDefinition"],
							msg: "Invalid function",
							type: "value_error",
						},
					],
				},
				"Fallback",
			),
		).toBe("body.functionDefinition: Invalid function");
	});

	it("rejects malformed or non-object JSON before making a request", async () => {
		const { result } = renderHook(() => useFunctionDefinitionForm());

		act(() => result.current.setFunctionDefinitionText("[1, 2]"));
		await act(() => result.current.validateFunctionDefinition());

		expect(result.current.functionDefinitionError).toBe(
			"Function definition must be a JSON object.",
		);
		expect(validateFilterFunction).not.toHaveBeenCalled();
		expect(parseFunctionDefinitionText("{").ok).toBe(false);
	});

	it("validates a parsed definition and stores its computed signature", async () => {
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
		const { result } = renderHook(() => useFunctionDefinitionForm());

		act(() =>
			result.current.setFunctionDefinitionText(
				JSON.stringify({ name: "literalString", value: "Alice" }),
			),
		);
		await act(() => result.current.validateFunctionDefinition());

		expect(validateFilterFunction).toHaveBeenCalledWith(
			{ functionDefinition: { name: "literalString", value: "Alice" } },
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);
		expect(result.current.formStatus).toEqual({
			status: "validated",
			signature: {
				args: [],
				output: { kind: "field", type: "string", mutable: false },
			},
		});
	});

	it("uploads the trimmed registry identity and reports conflicts", async () => {
		vi.mocked(createFilterFunction).mockResolvedValue({
			status: 409,
			data: { detail: "Function 'glossary.character-name' already exists." },
			headers: new Headers(),
		});
		const { result } = renderHook(() => useFunctionDefinitionForm());

		act(() => {
			result.current.setFunctionNamespace(" glossary ");
			result.current.setFunctionName(" character-name ");
			result.current.setFunctionDefinitionText(
				JSON.stringify({ name: "literalString", value: "Alice" }),
			);
		});
		await act(() => result.current.uploadFunctionDefinition());

		expect(createFilterFunction).toHaveBeenCalledWith(
			{
				functionDefinition: { name: "literalString", value: "Alice" },
				functionName: "character-name",
				namespace: "glossary",
			},
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);
		expect(result.current.formStatus).toEqual({
			status: "error",
			action: "upload",
			message: "Function 'glossary.character-name' already exists.",
		});
	});

	it("stores the created function after a successful upload", async () => {
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
		const { result } = renderHook(() => useFunctionDefinitionForm());

		act(() => {
			result.current.setFunctionNamespace("glossary");
			result.current.setFunctionName("character-name");
			result.current.setFunctionDefinitionText(
				JSON.stringify({ name: "literalString", value: "Alice" }),
			);
		});
		await act(() => result.current.uploadFunctionDefinition());

		expect(result.current.formStatus.status).toBe("uploaded");
		if (result.current.formStatus.status === "uploaded") {
			expect(result.current.formStatus.functionDefinition.functionDefinitionId).toBe(
				"function-1",
			);
		}
	});
});
