import { readLabelGroupsLabelGroupsGet } from "@/api/endpoints/default/default";
import {
	readFunctionsFiltersFunctionsGet,
	readWorkflowsFiltersWorkflowsGet,
} from "@/api/endpoints/filters/filters";
import type { FunctionDefinitionMeta, LabelGroup, WorkflowSummary } from "@/api/models";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAnnotationRunnerForm } from "./useAnnotationRunnerForm";
import { useLabelSourceRunnerForm } from "./useLabelSourceRunnerForm";
import { useWorkflowFunctionRunnerForm } from "./useWorkflowFunctionRunnerForm";

vi.mock("@/api/endpoints/default/default", () => ({
	readLabelGroupsLabelGroupsGet: vi.fn(),
}));

vi.mock("@/api/endpoints/filters/filters", () => ({
	readFunctionsFiltersFunctionsGet: vi.fn(),
	readWorkflowsFiltersWorkflowsGet: vi.fn(),
}));

const labelGroup: LabelGroup = {
	labelGroupId: "label-group-1",
	labelGroupName: "Characters",
	novelId: "novel-1",
};

const workflow: WorkflowSummary = {
	createdAt: "2026-08-05T00:00:00Z",
	jobId: null,
	schema: { kind: "schema", fields: {} },
	updatedAt: "2026-08-05T00:00:00Z",
	useCase: "advanced",
	workflowId: "workflow-1",
	workflowMessage: null,
	workflowName: "Labels",
	workflowStatus: "complete",
};

const functionDefinition: FunctionDefinitionMeta = {
	functionDefinitionId: "function-1",
	functionName: "lock",
	namespace: "labels",
};

describe("runner form hooks", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(readLabelGroupsLabelGroupsGet).mockResolvedValue({
			status: 200,
			data: [labelGroup],
			headers: new Headers(),
		});
		vi.mocked(readWorkflowsFiltersWorkflowsGet).mockResolvedValue({
			status: 200,
			data: [workflow],
			headers: new Headers(),
		});
		vi.mocked(readFunctionsFiltersFunctionsGet).mockResolvedValue({
			status: 200,
			data: [functionDefinition],
			headers: new Headers(),
		});
	});

	afterEach(() => vi.useRealTimers());

	it("searches completed novel workflows and saved functions after a debounce", async () => {
		vi.useFakeTimers();
		const { result } = renderHook(() =>
			useWorkflowFunctionRunnerForm("novel-1", true, "workflow"),
		);
		act(() => {
			result.current.workflows.setSearchKeyword("labels");
			result.current.functions.setSearchKeyword("lock");
		});

		await act(() => vi.advanceTimersByTimeAsync(250));

		expect(readWorkflowsFiltersWorkflowsGet).toHaveBeenCalledWith(
			{ novelId: "novel-1", status: "complete", search: "labels", limit: 100 },
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);
		expect(readFunctionsFiltersFunctionsGet).toHaveBeenCalledWith(
			{ search: "lock", limit: 100 },
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);
	});

	it("updates and resets the label-source form state", async () => {
		const { result } = renderHook(() => useLabelSourceRunnerForm("novel-1", true));
		await waitFor(() => expect(result.current.labelGroups.status).toBe("ready"));

		act(() => {
			result.current.setLabelGroupSearchKeyword("char");
			result.current.selectLabelGroup(labelGroup);
			result.current.setOutputWorkflowName(" Current labels ");
			result.current.preSend();
		});
		expect(result.current.formStatus).toEqual({ status: "submitting" });

		act(() => result.current.onSendSuccess());
		expect(result.current.formStatus).toEqual({ status: "succeeded", target: "workflow" });

		act(() => result.current.resetForm());
		expect(result.current.labelGroupKeyword).toBe("");
		expect(result.current.selectedLabelGroup).toBeNull();
		expect(result.current.outputWorkflowName).toBe("");
		expect(result.current.formStatus).toEqual({ status: "idle" });
	});

	it("keeps independent runner drafts and applies form-specific success targets", () => {
		const { result } = renderHook(() => ({
			map: useWorkflowFunctionRunnerForm("novel-1", true, "workflow"),
			filter: useWorkflowFunctionRunnerForm("novel-1", false, "workflow"),
			group: useWorkflowFunctionRunnerForm("novel-1", false, "grouping"),
		}));

		act(() => {
			result.current.map.selectWorkflow(workflow);
			result.current.map.selectFunctionDefinition(functionDefinition);
			result.current.map.setOutputWorkflowName(" Mapped ");
			result.current.filter.selectWorkflow(workflow);
			result.current.filter.selectFunctionDefinition(functionDefinition);
			result.current.group.selectWorkflow(workflow);
			result.current.group.selectFunctionDefinition(functionDefinition);
			result.current.map.preSend();
			result.current.filter.onSendError("Filter failed");
			result.current.group.onSendSuccess();
		});

		expect(result.current.map.outputWorkflowName).toBe(" Mapped ");
		expect(result.current.map.formStatus).toEqual({ status: "submitting" });
		expect(result.current.filter.formStatus).toEqual({
			status: "error",
			message: "Filter failed",
		});
		expect(result.current.group.formStatus).toEqual({
			status: "succeeded",
			target: "grouping",
		});
	});

	it("updates annotation fields with derived ids and resets the draft", () => {
		const { result } = renderHook(() => useAnnotationRunnerForm("novel-1", true));
		act(() => {
			result.current.selectWorkflow(workflow);
			const firstId = result.current.fields[0].id;
			result.current.setFieldName(firstId, "note");
			result.current.setFieldDefaultValue(firstId, "review");
			result.current.addField();
		});
		act(() => {
			const secondField = result.current.fields[1];
			result.current.setFieldName(secondField.id, "score");
			result.current.setFieldType(secondField.id, "float");
			result.current.setFieldDefaultValue(secondField.id, "0.75");
			result.current.onSendSuccess();
		});

		expect(result.current.fields.map((field) => field.id)).toEqual([0, 1]);
		expect(result.current.formStatus).toEqual({ status: "succeeded", target: "annotation" });

		act(() => result.current.resetForm());
		expect(result.current.selectedWorkflow).toBeNull();
		expect(result.current.fields).toEqual([
			{ id: 0, name: "", type: "string", defaultValue: "" },
		]);
		expect(result.current.formStatus).toEqual({ status: "idle" });
	});
});
