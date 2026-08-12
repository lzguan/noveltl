import { readLabelGroupsLabelGroupsGet } from "@/api/endpoints/default/default";
import {
	readFunctionsFiltersFunctionsGet,
	readWorkflowsFiltersWorkflowsGet,
	runPythonAnnotation,
	runPythonFilter,
	runPythonGroup,
	runPythonLabelSource,
	runPythonMap,
} from "@/api/endpoints/filters/filters";
import type {
	FunctionDefinitionMeta,
	GroupOperationAccepted,
	LabelGroup,
	WorkflowOperationAccepted,
	WorkflowSummary,
} from "@/api/models";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useLabelSourceRunnerForm } from "./useLabelSourceRunnerForm";
import { useAnnotationRunnerForm } from "./useAnnotationRunnerForm";
import { useMapRunnerForm } from "./useMapRunnerForm";
import { useRunnerPanel } from "./useRunnerPanel";

vi.mock("@/api/endpoints/default/default", () => ({
	readLabelGroupsLabelGroupsGet: vi.fn(),
}));

vi.mock("@/api/endpoints/filters/filters", () => ({
	readFunctionsFiltersFunctionsGet: vi.fn(),
	readWorkflowsFiltersWorkflowsGet: vi.fn(),
	runPythonAnnotation: vi.fn(),
	runPythonFilter: vi.fn(),
	runPythonGroup: vi.fn(),
	runPythonLabelSource: vi.fn(),
	runPythonMap: vi.fn(),
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

const workflowAccepted: WorkflowOperationAccepted = {
	jobId: "job-1",
	workflow: {
		...workflow,
		instanceCount: 0,
		jobId: "job-1",
		labelGroupIds: [],
		novelIds: ["novel-1"],
		workflowStatus: "pending",
	},
};

const groupAccepted: GroupOperationAccepted = {
	jobId: "job-2",
	grouping: {
		assignmentCount: 0,
		createdAt: "2026-08-05T00:00:00Z",
		functionDefinition,
		groupingId: "grouping-1",
		groupingMessage: null,
		groupingStatus: "pending",
		jobId: "job-2",
		outputType: "string",
		updatedAt: "2026-08-05T00:00:00Z",
		workflowId: workflow.workflowId,
	},
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
		vi.mocked(runPythonLabelSource).mockResolvedValue({
			status: 202,
			data: workflowAccepted,
			headers: new Headers(),
		});
		vi.mocked(runPythonAnnotation).mockResolvedValue({
			status: 202,
			data: workflowAccepted,
			headers: new Headers(),
		});
		vi.mocked(runPythonMap).mockResolvedValue({
			status: 202,
			data: workflowAccepted,
			headers: new Headers(),
		});
		vi.mocked(runPythonFilter).mockResolvedValue({
			status: 202,
			data: workflowAccepted,
			headers: new Headers(),
		});
		vi.mocked(runPythonGroup).mockResolvedValue({
			status: 202,
			data: groupAccepted,
			headers: new Headers(),
		});
	});

	afterEach(() => vi.useRealTimers());

	it("searches completed novel workflows and saved functions after a debounce", async () => {
		vi.useFakeTimers();
		const { result } = renderHook(() => useMapRunnerForm("novel-1", true));
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

	it("loads label groups and submits a trimmed label-source payload", async () => {
		const { result } = renderHook(() => useLabelSourceRunnerForm("novel-1", true));
		await waitFor(() => expect(result.current.labelGroups.status).toBe("ready"));

		act(() => {
			result.current.selectLabelGroup(labelGroup);
			result.current.setOutputWorkflowName(" Current labels ");
		});
		await act(() => result.current.submitLabelSourceRunner());

		expect(runPythonLabelSource).toHaveBeenCalledWith(
			{ labelGroupId: "label-group-1", outputName: "Current labels" },
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);
		expect(result.current.formStatus).toEqual({ status: "succeeded", target: "workflow" });
	});

	it("keeps independent drafts and sends exact map, filter, and group payloads", async () => {
		const { result } = renderHook(() => useRunnerPanel("novel-1", true));

		act(() => {
			result.current.mapForm.selectSourceWorkflow(workflow);
			result.current.mapForm.selectFunctionDefinition(functionDefinition);
			result.current.mapForm.setOutputWorkflowName(" Mapped ");
			result.current.filterForm.selectSourceWorkflow(workflow);
			result.current.filterForm.selectFunctionDefinition(functionDefinition);
			result.current.groupForm.selectWorkflow(workflow);
			result.current.groupForm.selectFunctionDefinition(functionDefinition);
			result.current.selectRunnerOperation("filter");
		});
		expect(result.current.mapForm.outputWorkflowName).toBe(" Mapped ");

		await act(() => result.current.mapForm.submitMapRunner());
		await act(() => result.current.filterForm.submitFilterRunner());
		await act(() => result.current.groupForm.submitGroupRunner());

		expect(runPythonMap).toHaveBeenCalledWith(
			{
				sourceWorkflowId: "workflow-1",
				functionDefinitionId: "function-1",
				outputName: "Mapped",
			},
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);
		expect(runPythonFilter).toHaveBeenCalledWith(
			{ sourceWorkflowId: "workflow-1", functionDefinitionId: "function-1" },
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);
		expect(runPythonGroup).toHaveBeenCalledWith(
			{ workflowId: "workflow-1", functionDefinitionId: "function-1" },
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);
	});

	it("submits typed annotation fields for a completed workflow", async () => {
		const { result } = renderHook(() => useAnnotationRunnerForm("novel-1", true));
		await waitFor(() => expect(result.current.workflows.results.status).toBe("ready"));
		act(() => {
			result.current.selectWorkflow(workflow);
			const firstId = result.current.fields[0].id;
			result.current.setFieldName(firstId, "note");
			result.current.setFieldDefaultValue(firstId, "review");
			result.current.addField();
		});
		act(() => {
			const score = result.current.fields[1];
			result.current.setFieldName(score.id, "score");
			result.current.setFieldType(score.id, "float");
			result.current.setFieldDefaultValue(score.id, "0.75");
			result.current.addField();
		});
		act(() => {
			const approved = result.current.fields[2];
			result.current.setFieldName(approved.id, "approved");
			result.current.setFieldType(approved.id, "bool");
			result.current.setFieldDefaultValue(approved.id, true);
		});

		await act(() => result.current.submitAnnotationRunner());

		expect(runPythonAnnotation).toHaveBeenCalledWith(
			{
				workflowId: "workflow-1",
				newFields: {
					note: { type: "string", defaultValue: "review" },
					score: { type: "float", defaultValue: 0.75 },
					approved: { type: "bool", defaultValue: true },
				},
			},
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);
		expect(result.current.formStatus).toEqual({
			status: "succeeded",
			target: "annotation",
		});
	});

	it("rejects duplicate and existing annotation field names before submission", async () => {
		const workflowWithField: WorkflowSummary = {
			...workflow,
			schema: { kind: "schema", fields: { note: { kind: "field", type: "string" } } },
		};
		const { result } = renderHook(() => useAnnotationRunnerForm("novel-1", true));
		act(() => {
			result.current.selectWorkflow(workflowWithField);
			result.current.setFieldName(result.current.fields[0].id, "note");
		});

		await act(() => result.current.submitAnnotationRunner());

		expect(runPythonAnnotation).not.toHaveBeenCalled();
		expect(result.current.formStatus).toEqual({
			status: "error",
			message: "Field 'note' already exists in the workflow.",
		});
	});

	it("surfaces backend compatibility errors", async () => {
		vi.mocked(runPythonMap).mockResolvedValue({
			status: 400,
			data: { detail: "Function output must be an object schema." },
			headers: new Headers(),
		});
		const { result } = renderHook(() => useRunnerPanel("novel-1", true));
		act(() => {
			result.current.mapForm.selectSourceWorkflow(workflow);
			result.current.mapForm.selectFunctionDefinition(functionDefinition);
		});

		await act(() => result.current.mapForm.submitMapRunner());

		expect(result.current.mapForm.formStatus).toEqual({
			status: "error",
			message: "Function output must be an object schema.",
		});
	});

	it("resets all drafts when the novel changes", async () => {
		const { result, rerender } = renderHook(({ novelId }) => useRunnerPanel(novelId, true), {
			initialProps: { novelId: "novel-1" },
		});
		act(() => {
			result.current.labelSourceForm.selectLabelGroup(labelGroup);
			result.current.mapForm.selectSourceWorkflow(workflow);
			result.current.mapForm.selectFunctionDefinition(functionDefinition);
		});

		rerender({ novelId: "novel-2" });

		await waitFor(() => expect(result.current.labelSourceForm.selectedLabelGroup).toBeNull());
		expect(result.current.mapForm.selectedWorkflow).toBeNull();
		expect(result.current.mapForm.selectedFunctionDefinition).toBeNull();
	});
});
