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
import { useAnnotationRunnerForm } from "../../hooks/runnerForms/useAnnotationRunnerForm";
import { useLabelSourceRunnerForm } from "../../hooks/runnerForms/useLabelSourceRunnerForm";
import { useWorkflowFunctionRunnerForm } from "../../hooks/runnerForms/useWorkflowFunctionRunnerForm";
import { AnnotationRunnerForm } from "./AnnotationRunnerForm";
import { FilterRunnerForm } from "./FilterRunnerForm";
import { GroupRunnerForm } from "./GroupRunnerForm";
import { LabelSourceRunnerForm } from "./LabelSourceRunnerForm";
import { MapRunnerForm } from "./MapRunnerForm";

vi.mock("@/api/endpoints/filters/filters", () => ({
	runPythonAnnotation: vi.fn(),
	runPythonFilter: vi.fn(),
	runPythonGroup: vi.fn(),
	runPythonLabelSource: vi.fn(),
	runPythonMap: vi.fn(),
}));
vi.mock("../../hooks/runnerForms/useAnnotationRunnerForm", () => ({
	useAnnotationRunnerForm: vi.fn(),
}));
vi.mock("../../hooks/runnerForms/useLabelSourceRunnerForm", () => ({
	useLabelSourceRunnerForm: vi.fn(),
}));
vi.mock("../../hooks/runnerForms/useWorkflowFunctionRunnerForm", () => ({
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

describe("runner form request payloads", () => {
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
		vi.mocked(useWorkflowFunctionRunnerForm).mockReturnValue(workflowFunctionForm());

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

	it("submits the selected label group and trimmed output name", async () => {
		render(<LabelSourceRunnerForm novelId="novel-1" enabled />);

		fireEvent.click(screen.getByRole("button", { name: "Create workflow" }));

		await waitFor(() =>
			expect(runPythonLabelSource).toHaveBeenCalledWith({
				labelGroupId: "label-group-1",
				outputName: "Current labels",
			}),
		);
	});

	it("submits the selected workflow, function, and trimmed map name", async () => {
		vi.mocked(useWorkflowFunctionRunnerForm).mockReturnValue(workflowFunctionForm(" Mapped "));
		render(<MapRunnerForm novelId="novel-1" enabled />);

		fireEvent.click(screen.getByRole("button", { name: "Create workflow" }));

		await waitFor(() =>
			expect(runPythonMap).toHaveBeenCalledWith({
				sourceWorkflowId: "workflow-1",
				functionDefinitionId: "function-1",
				outputName: "Mapped",
			}),
		);
	});

	it("omits an empty optional name from a filter request", async () => {
		render(<FilterRunnerForm novelId="novel-1" enabled />);

		fireEvent.click(screen.getByRole("button", { name: "Create workflow" }));

		await waitFor(() =>
			expect(runPythonFilter).toHaveBeenCalledWith({
				sourceWorkflowId: "workflow-1",
				functionDefinitionId: "function-1",
			}),
		);
	});

	it("submits the selected workflow and function for grouping", async () => {
		render(<GroupRunnerForm novelId="novel-1" enabled />);

		fireEvent.click(screen.getByRole("button", { name: "Create grouping" }));

		await waitFor(() =>
			expect(runPythonGroup).toHaveBeenCalledWith({
				workflowId: "workflow-1",
				functionDefinitionId: "function-1",
			}),
		);
	});

	it("submits validated annotation fields for the selected workflow", async () => {
		render(<AnnotationRunnerForm novelId="novel-1" enabled />);

		fireEvent.click(screen.getByRole("button", { name: "Add annotation fields" }));

		await waitFor(() =>
			expect(runPythonAnnotation).toHaveBeenCalledWith({
				workflowId: "workflow-1",
				newFields: { note: { type: "string", defaultValue: "" } },
			}),
		);
	});
});
