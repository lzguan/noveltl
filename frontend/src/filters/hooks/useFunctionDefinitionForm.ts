import { useState } from "react";
import type { FunctionDefinitionResponse, Signature } from "@/api/models";

type ParsedFunctionDefinition =
	| { ok: true; definition: Record<string, unknown> }
	| { ok: false; message: string };

function isJsonObject(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function parseFunctionDefinitionText(definitionText: string): ParsedFunctionDefinition {
	try {
		const parsed: unknown = JSON.parse(definitionText);
		if (!isJsonObject(parsed)) {
			return { ok: false, message: "Function definition must be a JSON object." };
		}
		return { ok: true, definition: parsed };
	} catch (error) {
		return {
			ok: false,
			message:
				error instanceof Error ? error.message : "Function definition is not valid JSON.",
		};
	}
}

export function useFunctionDefinitionForm() {
	const [functionNamespace, setFunctionNamespaceState] = useState("");
	const [functionName, setFunctionNameState] = useState("");
	const [functionDefinitionText, setFunctionDefinitionTextState] = useState("");
	const [functionDefinitionError, setFunctionDefinitionError] = useState<string | null>(null);
	const [formStatus, setFormStatus] = useState<
		| { status: "idle" }
		| { status: "validating" }
		| { status: "validated"; signature: Signature }
		| { status: "uploading" }
		| { status: "uploaded"; functionDefinition: FunctionDefinitionResponse }
		| { status: "error"; action: "validate" | "upload"; message: string }
	>({ status: "idle" });

	function resetRequestState() {
		setFormStatus({ status: "idle" });
	}

	function setFunctionNamespace(namespace: string) {
		setFunctionNamespaceState(namespace);
		resetRequestState();
	}

	function setFunctionName(name: string) {
		setFunctionNameState(name);
		resetRequestState();
	}

	function setFunctionDefinitionText(definitionText: string) {
		setFunctionDefinitionTextState(definitionText);
		setFunctionDefinitionError(null);
		resetRequestState();
	}

	function preSend(action: "validate" | "upload") {
		setFormStatus({ status: action === "validate" ? "validating" : "uploading" });
	}

	function onSendError(action: "validate" | "upload", message: string) {
		setFormStatus({ status: "error", action, message });
	}

	function onSendSuccess(
		result:
			| { action: "validate"; signature: Signature }
			| { action: "upload"; functionDefinition: FunctionDefinitionResponse },
	) {
		if (result.action === "validate") {
			setFormStatus({ status: "validated", signature: result.signature });
		} else {
			setFormStatus({ status: "uploaded", functionDefinition: result.functionDefinition });
		}
	}

	function resetForm() {
		setFunctionNamespaceState("");
		setFunctionNameState("");
		setFunctionDefinitionTextState("");
		setFunctionDefinitionError(null);
		setFormStatus({ status: "idle" });
	}

	return {
		functionNamespace,
		functionName,
		functionDefinitionText,
		functionDefinitionError,
		formStatus,
		setFunctionNamespace,
		setFunctionName,
		setFunctionDefinitionText,
		setFunctionDefinitionError,
		preSend,
		onSendError,
		onSendSuccess,
		resetForm,
	};
}
