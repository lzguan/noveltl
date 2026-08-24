import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
	parseFunctionDefinitionText,
	useFunctionDefinitionForm,
} from "./useFunctionDefinitionForm";

describe("useFunctionDefinitionForm", () => {
	it("parses JSON objects and rejects other JSON values", () => {
		expect(parseFunctionDefinitionText('{"name":"literalString"}')).toEqual({
			ok: true,
			definition: { name: "literalString" },
		});
		expect(parseFunctionDefinitionText("[1, 2]")).toEqual({
			ok: false,
			message: "Function definition must be a JSON object.",
		});
		expect(parseFunctionDefinitionText("{").ok).toBe(false);
	});

	it("applies validation and upload lifecycle transitions", () => {
		const { result } = renderHook(() => useFunctionDefinitionForm());

		act(() => result.current.preSend("validate"));
		expect(result.current.formStatus).toEqual({ status: "validating" });

		act(() =>
			result.current.onSendSuccess({
				action: "validate",
				signature: {
					args: [],
					output: { kind: "field", type: "string", mutable: false },
				},
			}),
		);
		expect(result.current.formStatus.status).toBe("validated");

		act(() => result.current.preSend("upload"));
		expect(result.current.formStatus).toEqual({ status: "uploading" });

		act(() => result.current.onSendError("upload", "Already exists."));
		expect(result.current.formStatus).toEqual({
			status: "error",
			action: "upload",
			message: "Already exists.",
		});
	});

	it("clears stale request state when edited and resets the full form", () => {
		const { result } = renderHook(() => useFunctionDefinitionForm());

		act(() => {
			result.current.setFunctionNamespace("glossary");
			result.current.setFunctionName("character-name");
			result.current.setFunctionDefinitionText('{"name":"literalString"}');
			result.current.setFunctionDefinitionError("Invalid definition");
			result.current.onSendError("validate", "Validation failed");
		});
		act(() => result.current.setFunctionName("speaker-name"));
		expect(result.current.formStatus).toEqual({ status: "idle" });

		act(() => result.current.resetForm());
		expect(result.current.functionNamespace).toBe("");
		expect(result.current.functionName).toBe("");
		expect(result.current.functionDefinitionText).toBe("");
		expect(result.current.functionDefinitionError).toBeNull();
		expect(result.current.formStatus).toEqual({ status: "idle" });
	});
});
