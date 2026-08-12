import type { FunctionDefinitionMeta, LabelGroup, WorkflowSummary } from "@/api/models";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { RunnerPanelModel, SearchOptionsModel } from "../types";
import { RunnerPanel } from "./RunnerPanel";

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

function searchOptions<T>(items: readonly T[]): SearchOptionsModel<T> {
	return {
		keyword: "",
		results: { status: "ready", data: items },
		setSearchKeyword: vi.fn(),
	};
}

function createModel(): RunnerPanelModel {
	return {
		activeRunnerOperation: "labelSource",
		selectRunnerOperation: vi.fn(),
		labelSourceForm: {
			labelGroups: { status: "ready", data: [labelGroup] },
			labelGroupKeyword: "",
			selectedLabelGroup: null,
			outputWorkflowName: "",
			formStatus: { status: "idle" },
			setLabelGroupSearchKeyword: vi.fn(),
			selectLabelGroup: vi.fn(),
			setOutputWorkflowName: vi.fn(),
			submitLabelSourceRunner: vi.fn(async () => {}),
		},
		annotationForm: {
			workflows: searchOptions([workflow]),
			selectedWorkflow: workflow,
			fields: [{ id: 1, name: "note", type: "string", defaultValue: "" }],
			formStatus: { status: "idle" },
			selectWorkflow: vi.fn(),
			addField: vi.fn(),
			removeField: vi.fn(),
			setFieldName: vi.fn(),
			setFieldType: vi.fn(),
			setFieldDefaultValue: vi.fn(),
			submitAnnotationRunner: vi.fn(async () => {}),
		},
		mapForm: {
			workflows: searchOptions([workflow]),
			functions: searchOptions([functionDefinition]),
			selectedWorkflow: workflow,
			selectedFunctionDefinition: functionDefinition,
			outputWorkflowName: "",
			formStatus: { status: "idle" },
			selectSourceWorkflow: vi.fn(),
			selectFunctionDefinition: vi.fn(),
			setOutputWorkflowName: vi.fn(),
			submitMapRunner: vi.fn(async () => {}),
		},
		filterForm: {
			workflows: searchOptions([workflow]),
			functions: searchOptions([functionDefinition]),
			selectedWorkflow: workflow,
			selectedFunctionDefinition: functionDefinition,
			outputWorkflowName: "",
			formStatus: { status: "idle" },
			selectSourceWorkflow: vi.fn(),
			selectFunctionDefinition: vi.fn(),
			setOutputWorkflowName: vi.fn(),
			submitFilterRunner: vi.fn(async () => {}),
		},
		groupForm: {
			workflows: searchOptions([workflow]),
			functions: searchOptions([functionDefinition]),
			selectedWorkflow: workflow,
			selectedFunctionDefinition: functionDefinition,
			formStatus: { status: "idle" },
			selectWorkflow: vi.fn(),
			selectFunctionDefinition: vi.fn(),
			submitGroupRunner: vi.fn(async () => {}),
		},
	};
}

describe("RunnerPanel", () => {
	it("renders runner forms and selects operations semantically", () => {
		const model = createModel();
		const { rerender } = render(<RunnerPanel {...model} />);

		expect(screen.getByLabelText("Label group")).toBeInTheDocument();
		expect(screen.getByLabelText("Output workflow name")).toBeInTheDocument();
		fireEvent.click(screen.getByRole("radio", { name: "Map" }));
		expect(model.selectRunnerOperation).toHaveBeenCalledWith("map");

		const mapModel: RunnerPanelModel = { ...model, activeRunnerOperation: "map" };
		rerender(<RunnerPanel {...mapModel} />);
		expect(screen.getByLabelText("Source workflow")).toBeInTheDocument();
		expect(screen.getByLabelText("Function")).toBeInTheDocument();
		expect(screen.getByLabelText("Output workflow name")).toBeInTheDocument();

		const annotationModel: RunnerPanelModel = {
			...model,
			activeRunnerOperation: "annotation",
		};
		rerender(<RunnerPanel {...annotationModel} />);
		expect(screen.getByLabelText("Workflow")).toBeInTheDocument();
		expect(screen.getByLabelText("Field name")).toBeInTheDocument();
		expect(screen.getByLabelText("Default value")).toBeInTheDocument();

		const groupModel: RunnerPanelModel = { ...model, activeRunnerOperation: "group" };
		rerender(<RunnerPanel {...groupModel} />);
		expect(screen.getByLabelText("Workflow")).toBeInTheDocument();
		expect(screen.getByLabelText("Function")).toBeInTheDocument();
		expect(screen.queryByLabelText("Output workflow name")).not.toBeInTheDocument();
	});

	it("reports accepted operations without exposing target identifiers", () => {
		const model = createModel();
		model.mapForm.formStatus = { status: "succeeded", target: "workflow" };
		model.activeRunnerOperation = "map";

		render(<RunnerPanel {...model} />);

		expect(screen.getByText("Workflow created and queued")).toBeInTheDocument();
		expect(screen.queryByText("workflow-1")).not.toBeInTheDocument();
	});
});
