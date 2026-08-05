import { createFilterFunction, validateFilterFunction } from "@/api/endpoints/filters/filters";
import { useCallback, useEffect, useRef, useState } from "react";
import { apiErrorMessage, requestErrorMessage } from "../apiErrors";
import type { FunctionDefinitionFormModel, FunctionDefinitionFormStatus } from "../types";

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

export function useFunctionDefinitionForm(): FunctionDefinitionFormModel {
	const [functionNamespace, setFunctionNamespaceState] = useState("");
	const [functionName, setFunctionNameState] = useState("");
	const [functionDefinitionText, setFunctionDefinitionTextState] = useState("");
	const [functionDefinitionError, setFunctionDefinitionError] = useState<string | null>(null);
	const [formStatus, setFormStatus] = useState<FunctionDefinitionFormStatus>({ status: "idle" });
	const activeRequest = useRef<AbortController | null>(null);

	const cancelActiveRequest = useCallback(() => {
		activeRequest.current?.abort();
		activeRequest.current = null;
	}, []);

	useEffect(() => cancelActiveRequest, [cancelActiveRequest]);

	const resetRequestState = useCallback(() => {
		cancelActiveRequest();
		setFormStatus({ status: "idle" });
	}, [cancelActiveRequest]);

	const setFunctionNamespace = useCallback(
		(namespace: string) => {
			setFunctionNamespaceState(namespace);
			resetRequestState();
		},
		[resetRequestState],
	);

	const setFunctionName = useCallback(
		(name: string) => {
			setFunctionNameState(name);
			resetRequestState();
		},
		[resetRequestState],
	);

	const setFunctionDefinitionText = useCallback(
		(definitionText: string) => {
			setFunctionDefinitionTextState(definitionText);
			setFunctionDefinitionError(null);
			resetRequestState();
		},
		[resetRequestState],
	);

	const readFunctionDefinition = useCallback(() => {
		const parsed = parseFunctionDefinitionText(functionDefinitionText);
		if (!parsed.ok) {
			setFunctionDefinitionError(parsed.message);
			return null;
		}
		setFunctionDefinitionError(null);
		return parsed.definition;
	}, [functionDefinitionText]);

	const validateFunctionDefinition = useCallback(async () => {
		const definition = readFunctionDefinition();
		if (definition === null) return;

		cancelActiveRequest();
		const controller = new AbortController();
		activeRequest.current = controller;
		setFormStatus({ status: "validating" });
		try {
			const response = await validateFilterFunction(
				{ functionDefinition: definition },
				{ signal: controller.signal },
			);
			if (controller.signal.aborted) return;
			if (response.status === 200) {
				setFormStatus({ status: "validated", signature: response.data.signature });
			} else {
				setFormStatus({
					status: "error",
					action: "validate",
					message: apiErrorMessage(response.data, "Function definition is invalid."),
				});
			}
		} catch (error) {
			if (!controller.signal.aborted) {
				setFormStatus({
					status: "error",
					action: "validate",
					message: requestErrorMessage(error),
				});
			}
		} finally {
			if (activeRequest.current === controller) activeRequest.current = null;
		}
	}, [cancelActiveRequest, readFunctionDefinition]);

	const uploadFunctionDefinition = useCallback(async () => {
		const definition = readFunctionDefinition();
		if (definition === null) return;

		cancelActiveRequest();
		const controller = new AbortController();
		activeRequest.current = controller;
		setFormStatus({ status: "uploading" });
		try {
			const response = await createFilterFunction(
				{
					functionDefinition: definition,
					functionName: functionName.trim(),
					namespace: functionNamespace.trim(),
				},
				{ signal: controller.signal },
			);
			if (controller.signal.aborted) return;
			if (response.status === 201) {
				setFormStatus({ status: "uploaded", functionDefinition: response.data });
			} else {
				setFormStatus({
					status: "error",
					action: "upload",
					message: apiErrorMessage(
						response.data,
						"Function definition could not be uploaded.",
					),
				});
			}
		} catch (error) {
			if (!controller.signal.aborted) {
				setFormStatus({
					status: "error",
					action: "upload",
					message: requestErrorMessage(error),
				});
			}
		} finally {
			if (activeRequest.current === controller) activeRequest.current = null;
		}
	}, [cancelActiveRequest, functionName, functionNamespace, readFunctionDefinition]);

	return {
		functionNamespace,
		functionName,
		functionDefinitionText,
		functionDefinitionError,
		formStatus,
		setFunctionNamespace,
		setFunctionName,
		setFunctionDefinitionText,
		validateFunctionDefinition,
		uploadFunctionDefinition,
	};
}
