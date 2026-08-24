import type { WorkflowSummary } from "@/api/models";
import { useCallback, useState } from "react";
import { useAsyncSearch } from "../useAsyncSearch";
import { fetchCompletedWorkflowOptions } from "./useRunnerOptions";

type AnnotationFieldType = "string" | "int" | "float" | "bool";

interface AnnotationFieldDraft {
	id: number;
	name: string;
	type: AnnotationFieldType;
	defaultValue: string | boolean;
}

const INITIAL_ANNOTATION_FIELD: AnnotationFieldDraft = {
	id: 0,
	name: "",
	type: "string",
	defaultValue: "",
};

function defaultValue(type: AnnotationFieldType): string | boolean {
	return type === "bool" ? false : type === "string" ? "" : "0";
}

function nextFieldId(fields: readonly AnnotationFieldDraft[]) {
	return fields.reduce((highestId, field) => Math.max(highestId, field.id), -1) + 1;
}

export function useAnnotationRunnerForm(novelId: string, enabled: boolean) {
	const fetchWorkflows = useCallback(
		(keyword: string, signal: AbortSignal) =>
			fetchCompletedWorkflowOptions(novelId, keyword, signal),
		[novelId],
	);
	const workflows = useAsyncSearch(fetchWorkflows, enabled);
	const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowSummary | null>(null);
	const [fields, setFields] = useState<readonly AnnotationFieldDraft[]>([
		INITIAL_ANNOTATION_FIELD,
	]);
	const [formStatus, setFormStatus] = useState<
		| { status: "idle" }
		| { status: "submitting" }
		| { status: "succeeded"; target: "annotation" }
		| { status: "error"; message: string }
	>({ status: "idle" });

	function resetRequestStatus() {
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
							id: nextFieldId(current),
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

	function preSend() {
		setFormStatus({ status: "submitting" });
	}

	function onSendError(message: string) {
		setFormStatus({ status: "error", message });
	}

	function onSendSuccess() {
		setFormStatus({ status: "succeeded", target: "annotation" });
	}

	function resetForm() {
		setSelectedWorkflow(null);
		setFields([INITIAL_ANNOTATION_FIELD]);
		workflows.setSearchKeyword("");
		setFormStatus({ status: "idle" });
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
		preSend,
		onSendError,
		onSendSuccess,
		resetForm,
	};
}
