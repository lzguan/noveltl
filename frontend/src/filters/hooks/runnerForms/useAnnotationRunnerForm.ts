import { runPythonAnnotation } from "@/api/endpoints/filters/filters";
import type { NewFieldRequest, WorkflowSummary } from "@/api/models";
import { useCallback, useEffect, useRef, useState } from "react";
import { apiErrorMessage, requestErrorMessage } from "../../apiErrors";
import type {
	AnnotationFieldDraft,
	AnnotationFieldType,
	AnnotationRunnerFormModel,
	RunnerFormStatus,
} from "../../types";
import { useAsyncSearch } from "../useAsyncSearch";
import { fetchCompletedWorkflowOptions } from "./useRunnerOptions";

function defaultValue(type: AnnotationFieldType): string | boolean {
	return type === "bool" ? false : type === "string" ? "" : "0";
}

function newFieldRequest(field: AnnotationFieldDraft): NewFieldRequest {
	if (field.type === "string") {
		return {
			type: "string",
			defaultValue: typeof field.defaultValue === "string" ? field.defaultValue : "",
		};
	}
	if (field.type === "bool") {
		return {
			type: "bool",
			defaultValue: field.defaultValue === true,
		};
	}
	const text = typeof field.defaultValue === "string" ? field.defaultValue : "";
	if (text.trim() === "") throw new Error(`Enter a default value for '${field.name.trim()}'.`);
	const parsed = Number(text);
	if (field.type === "int") {
		if (!Number.isInteger(parsed)) {
			throw new Error(`The default for '${field.name.trim()}' must be a whole number.`);
		}
		return { type: "int", defaultValue: parsed };
	}
	if (!Number.isFinite(parsed)) {
		throw new Error(`The default for '${field.name.trim()}' must be a finite number.`);
	}
	return { type: "float", defaultValue: parsed };
}

function buildNewFields(
	workflow: WorkflowSummary,
	fields: readonly AnnotationFieldDraft[],
): Record<string, NewFieldRequest> {
	if (fields.length === 0) throw new Error("Add at least one annotation field.");
	const newFields: Record<string, NewFieldRequest> = {};
	for (const field of fields) {
		const name = field.name.trim();
		if (!name) throw new Error("Every annotation field needs a name.");
		if (name.length > 128) throw new Error(`Field '${name}' exceeds 128 characters.`);
		if (name in newFields) throw new Error(`Annotation field '${name}' is duplicated.`);
		if (name in (workflow.schema.fields ?? {})) {
			throw new Error(`Field '${name}' already exists in the workflow.`);
		}
		newFields[name] = newFieldRequest(field);
	}
	return newFields;
}

export function useAnnotationRunnerForm(
	novelId: string,
	enabled: boolean,
): AnnotationRunnerFormModel {
	const fetchWorkflows = useCallback(
		(keyword: string, signal: AbortSignal) =>
			fetchCompletedWorkflowOptions(novelId, keyword, signal),
		[novelId],
	);
	const workflows = useAsyncSearch(fetchWorkflows, enabled);
	const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowSummary | null>(null);
	const nextFieldId = useRef(1);
	const [fields, setFields] = useState<readonly AnnotationFieldDraft[]>([
		{ id: 0, name: "", type: "string", defaultValue: "" },
	]);
	const [formStatus, setFormStatus] = useState<RunnerFormStatus>({ status: "idle" });
	const activeRequest = useRef<AbortController | null>(null);
	const setWorkflowSearchKeyword = workflows.setSearchKeyword;

	const cancelActiveRequest = useCallback(() => {
		activeRequest.current?.abort();
		activeRequest.current = null;
	}, []);

	useEffect(() => cancelActiveRequest, [cancelActiveRequest]);

	useEffect(() => {
		cancelActiveRequest();
		setSelectedWorkflow(null);
		setFields([{ id: nextFieldId.current++, name: "", type: "string", defaultValue: "" }]);
		setWorkflowSearchKeyword("");
		setFormStatus({ status: "idle" });
	}, [cancelActiveRequest, novelId, setWorkflowSearchKeyword]);

	useEffect(() => {
		if (!enabled) {
			cancelActiveRequest();
			setFormStatus({ status: "idle" });
		}
	}, [cancelActiveRequest, enabled]);

	function resetRequestStatus() {
		cancelActiveRequest();
		setFormStatus({ status: "idle" });
	}

	function selectWorkflow(workflow: WorkflowSummary | null) {
		setSelectedWorkflow(workflow);
		resetRequestStatus();
	}

	function updateField(
		id: number,
		update: (field: AnnotationFieldDraft) => AnnotationFieldDraft,
	) {
		setFields((current) => current.map((field) => (field.id === id ? update(field) : field)));
		resetRequestStatus();
	}

	function addField() {
		setFields((current) =>
			current.length >= 100
				? current
				: [
						...current,
						{
							id: nextFieldId.current++,
							name: "",
							type: "string",
							defaultValue: "",
						},
					],
		);
		resetRequestStatus();
	}

	function removeField(id: number) {
		setFields((current) => current.filter((field) => field.id !== id));
		resetRequestStatus();
	}

	function setFieldName(id: number, name: string) {
		updateField(id, (field) => ({ ...field, name }));
	}

	function setFieldType(id: number, type: AnnotationFieldType) {
		updateField(id, (field) => ({ ...field, type, defaultValue: defaultValue(type) }));
	}

	function setFieldDefaultValue(id: number, value: string | boolean) {
		updateField(id, (field) => ({ ...field, defaultValue: value }));
	}

	async function submitAnnotationRunner() {
		if (!selectedWorkflow) return;
		let newFields: Record<string, NewFieldRequest>;
		try {
			newFields = buildNewFields(selectedWorkflow, fields);
		} catch (error) {
			setFormStatus({ status: "error", message: requestErrorMessage(error) });
			return;
		}

		cancelActiveRequest();
		const controller = new AbortController();
		activeRequest.current = controller;
		setFormStatus({ status: "submitting" });
		try {
			const response = await runPythonAnnotation(
				{ workflowId: selectedWorkflow.workflowId, newFields },
				{ signal: controller.signal },
			);
			if (controller.signal.aborted) return;
			if (response.status === 202) {
				setFormStatus({ status: "succeeded", target: "annotation" });
			} else {
				setFormStatus({
					status: "error",
					message: apiErrorMessage(
						response.data,
						"Could not queue the annotation workflow.",
					),
				});
			}
		} catch (error) {
			if (!controller.signal.aborted) {
				setFormStatus({ status: "error", message: requestErrorMessage(error) });
			}
		} finally {
			if (activeRequest.current === controller) activeRequest.current = null;
		}
	}

	return {
		workflows,
		selectedWorkflow,
		fields,
		formStatus,
		selectWorkflow,
		addField,
		removeField,
		setFieldName,
		setFieldType,
		setFieldDefaultValue,
		submitAnnotationRunner,
	};
}
