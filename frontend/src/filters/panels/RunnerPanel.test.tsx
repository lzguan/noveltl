import {
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
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAnnotationRunnerForm } from "../hooks/runnerForms/useAnnotationRunnerForm";
import { useLabelSourceRunnerForm } from "../hooks/runnerForms/useLabelSourceRunnerForm";
import { useWorkflowFunctionRunnerForm } from "../hooks/runnerForms/useWorkflowFunctionRunnerForm";
import { RunnerPanel } from "./RunnerPanel";

vi.mock("@/api/endpoints/filters/filters", () => ({
	runPythonAnnotation: vi.fn(),
	runPythonFilter: vi.fn(),
	runPythonGroup: vi.fn(),
	runPythonLabelSource: vi.fn(),
	runPythonMap: vi.fn(),
}));

vi.mock("../hooks/runnerForms/useAnnotationRunnerForm", () => ({
	useAnnotationRunnerForm: vi.fn(),
}));
vi.mock("../hooks/runnerForms/useLabelSourceRunnerForm", () => ({
	useLabelSourceRunnerForm: vi.fn(),
}));
vi.mock("../hooks/runnerForms/useWorkflowFunctionRunnerForm", () => ({
	useWorkflowFunctionRunnerForm: vi.fn(),
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

function lifecycle() {
	return {
		preSend: vi.fn(),
		onSendError: vi.fn(),
		onSendSuccess: vi.fn(),
		resetForm: vi.fn(),
	};
}

function search<T>(data: readonly T[]) {
	return {
		keyword: "",
		results: { status: "ready" as const, data },
		setSearchKeyword: vi.fn(),
	};
}

function workflowFunctionForm(outputWorkflowName = "") {
	return {
		workflows: search([workflow]),
		functions: search([functionDefinition]),
		selectedWorkflow: workflow,
		selectedFunctionDefinition: functionDefinition,
		outputWorkflowName,
		formStatus: { status: "idle" as const },
		selectWorkflow: vi.fn(),
		selectFunctionDefinition: vi.fn(),
		setOutputWorkflowName: vi.fn(),
		...lifecycle(),
	};
}

describe("RunnerPanel", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(useLabelSourceRunnerForm).mockReturnValue({
			labelGroups: { status: "ready", data: [labelGroup] },
			labelGroupKeyword: "",
			selectedLabelGroup: labelGroup,
			outputWorkflowName: " Current labels ",
			formStatus: { status: "idle" },
			setLabelGroupSearchKeyword: vi.fn(),
			selectLabelGroup: vi.fn(),
			setOutputWorkflowName: vi.fn(),
			...lifecycle(),
		});
		vi.mocked(useAnnotationRunnerForm).mockReturnValue({
			workflows: search([workflow]),
			selectedWorkflow: workflow,
			fields: [{ id: 0, name: "note", type: "string", defaultValue: "" }],
			formStatus: { status: "idle" },
			selectWorkflow: vi.fn(),
			addField: vi.fn(),
			removeField: vi.fn(),
			setFieldName: vi.fn(),
			setFieldType: vi.fn(),
			setFieldDefaultValue: vi.fn(),
			...lifecycle(),
		});
		vi.mocked(useWorkflowFunctionRunnerForm).mockReturnValue(workflowFunctionForm(" Mapped "));

		for (const request of [
			runPythonAnnotation,
			runPythonFilter,
			runPythonLabelSource,
			runPythonMap,
		]) {
			vi.mocked(request).mockResolvedValue({
				status: 202,
				data: workflowAccepted,
				headers: new Headers(),
			});
		}
		vi.mocked(runPythonGroup).mockResolvedValue({
			status: 202,
			data: groupAccepted,
			headers: new Headers(),
		});
	});

	it("switches between runner forms", () => {
		render(<RunnerPanel novelId="novel-1" enabled />);
		expect(screen.getByLabelText("Label group")).toBeVisible();

		fireEvent.click(screen.getByRole("radio", { name: "Map" }));
		expect(screen.getByLabelText("Source workflow")).toBeVisible();
		expect(screen.getByLabelText("Function")).toBeVisible();

		fireEvent.click(screen.getByRole("radio", { name: "Group" }));
		expect(screen.getByLabelText("Workflow")).toBeVisible();
		expect(screen.queryByLabelText("Output workflow name")).not.toBeInTheDocument();
	});

	it("constructs each runner request in its form component", async () => {
		render(<RunnerPanel novelId="novel-1" enabled />);

		fireEvent.click(screen.getByRole("button", { name: "Create workflow" }));
		await waitFor(() => expect(runPythonLabelSource).toHaveBeenCalled());
		expect(runPythonLabelSource).toHaveBeenCalledWith({
			labelGroupId: "label-group-1",
			outputName: "Current labels",
		});

		fireEvent.click(screen.getByRole("radio", { name: "Map" }));
		fireEvent.click(screen.getByRole("button", { name: "Create workflow" }));
		await waitFor(() => expect(runPythonMap).toHaveBeenCalled());
		expect(runPythonMap).toHaveBeenCalledWith({
			sourceWorkflowId: "workflow-1",
			functionDefinitionId: "function-1",
			outputName: "Mapped",
		});

		vi.mocked(useWorkflowFunctionRunnerForm).mockReturnValue(workflowFunctionForm());
		fireEvent.click(screen.getByRole("radio", { name: "Filter" }));
		fireEvent.click(screen.getByRole("button", { name: "Create workflow" }));
		await waitFor(() => expect(runPythonFilter).toHaveBeenCalled());

		vi.mocked(useWorkflowFunctionRunnerForm).mockReturnValue(workflowFunctionForm());
		fireEvent.click(screen.getByRole("radio", { name: "Group" }));
		fireEvent.click(screen.getByRole("button", { name: "Create grouping" }));
		await waitFor(() => expect(runPythonGroup).toHaveBeenCalled());

		fireEvent.click(screen.getByRole("radio", { name: "Annotation" }));
		fireEvent.click(screen.getByRole("button", { name: "Add annotation fields" }));
		await waitFor(() => expect(runPythonAnnotation).toHaveBeenCalled());
		expect(runPythonAnnotation).toHaveBeenCalledWith({
			workflowId: "workflow-1",
			newFields: { note: { type: "string", defaultValue: "" } },
		});
	});
});
