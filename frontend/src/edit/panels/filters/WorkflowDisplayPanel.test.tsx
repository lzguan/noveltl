import type { ActiveGroupingState, WorkflowDisplayPanelProps } from "./WorkflowDisplayPanel";
import type {
	GroupingSectionModel,
	InstanceResultsModel,
	QuerySectionModel,
	WorkflowSelectionModel,
} from "./types";
import type {
	GroupingResponse,
	InstanceQueryResult,
	WorkflowResponse,
	WorkflowSummary,
} from "@/api/models";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkflowDisplayPanel } from "./WorkflowDisplayPanel";

const workflowSummary: WorkflowSummary = {
	createdAt: "2026-08-01T00:00:00Z",
	jobId: null,
	schema: {
		obj: true,
		fields: {
			title: { type: "string" },
			rank: { type: "int" },
			published: { type: "bool" },
			excerpt: { type: "textSpan" },
			character: { type: "labelRef" },
		},
	},
	updatedAt: "2026-08-01T00:00:00Z",
	useCase: "advanced",
	workflowId: "workflow-11111111",
	workflowMessage: null,
	workflowName: "Chapter candidates",
	workflowStatus: "complete",
};

const workflow: WorkflowResponse = {
	...workflowSummary,
	instanceCount: 1234,
	labelGroupIds: [],
	novelIds: ["novel-1"],
};

const speakerGrouping: GroupingResponse = {
	assignmentCount: 1234,
	createdAt: "2026-08-01T00:00:00Z",
	functionDefinition: {
		functionDefinitionId: "function-1",
		functionName: "speaker",
		namespace: "dialogue",
	},
	groupingId: "grouping-speaker",
	groupingMessage: null,
	groupingStatus: "complete",
	jobId: "job-1",
	outputType: "string",
	updatedAt: "2026-08-01T00:00:00Z",
	workflowId: workflow.workflowId,
};

const chapterGrouping: GroupingResponse = {
	...speakerGrouping,
	functionDefinition: {
		functionDefinitionId: "function-2",
		functionName: "chapter_number",
		namespace: "chapter",
	},
	groupingId: "grouping-chapter",
	outputType: "int",
};

const result: InstanceQueryResult = {
	instance: {
		instanceId: "instance-12345678",
		workflowId: workflow.workflowId,
		value: {
			obj: true,
			fields: {
				title: { type: "string", value: "A quiet promise" },
				rank: { type: "int", value: 7 },
				published: { type: "bool", value: true },
				excerpt: {
					type: "textSpan",
					value: {
						chapterId: "chapter-abcdefgh",
						chapterContentId: "content-1",
						start: 12,
						end: 28,
					},
				},
				character: {
					type: "labelRef",
					value: {
						chapterId: "chapter-abcdefgh",
						chapterContentId: "content-1",
						labelDataId: "label-data-1",
						labelGroupId: "label-group-1",
						labelId: "label-abcdefgh",
					},
				},
			},
		},
	},
	groupValues: {
		"grouping-speaker": { type: "string", value: "Lin" },
		"grouping-chapter": { type: "int", value: 4 },
	},
};

function activeGroupingStates() {
	const speaker: ActiveGroupingState = {
		grouping: speakerGrouping,
		search: "",
		selectedValues: [{ type: "string", value: "Lin" }],
		values: {
			status: "ready",
			data: {
				items: [
					{ value: { type: "string", value: "Lin" }, count: 18 },
					{ value: { type: "string", value: "Mei" }, count: 12 },
				],
				start: 1,
				end: 2,
				total: 51,
				hasPrevious: false,
				hasNext: true,
			},
		},
	};
	const chapter: ActiveGroupingState = {
		grouping: chapterGrouping,
		search: "",
		selectedValues: [],
		values: {
			status: "ready",
			data: {
				items: [{ value: { type: "int", value: 4 }, count: 30 }],
				start: 1,
				end: 1,
				total: 1,
				hasPrevious: false,
				hasNext: false,
			},
		},
	};
	return new Map([
		[speakerGrouping.groupingId, speaker],
		[chapterGrouping.groupingId, chapter],
	]);
}

interface PropsOverrides {
	workflowSelection?: Partial<WorkflowSelectionModel>;
	groupingSection?: Partial<GroupingSectionModel>;
	querySection?: Partial<QuerySectionModel>;
	instanceResults?: Partial<InstanceResultsModel>;
}

function createProps(overrides: PropsOverrides = {}): WorkflowDisplayPanelProps {
	const props: WorkflowDisplayPanelProps = {
		workflowSelection: {
			workflows: { status: "ready", data: [workflowSummary] },
			searchText: "",
			activeWorkflowId: workflow.workflowId,
			activeWorkflow: { status: "ready", data: workflow },
			setWorkflowSearchText: vi.fn(),
			selectWorkflow: vi.fn(),
		},
		groupingSection: {
			availableGroupings: {
				status: "ready",
				data: [speakerGrouping, chapterGrouping],
			},
			activeGroupings: activeGroupingStates(),
			activateGrouping: vi.fn(),
			deactivateGrouping: vi.fn(),
			setGroupingValueSearchText: vi.fn(),
			setGroupingValueSelected: vi.fn(),
			loadPreviousGroupingValuesPage: vi.fn(),
			loadNextGroupingValuesPage: vi.fn(),
		},
		querySection: {
			sortKeys: [{ fieldName: "rank", direction: "desc" }],
			queryStatus: { status: "idle" },
			addSortKey: vi.fn(),
			removeSortKey: vi.fn(),
			setSortKeyField: vi.fn(),
			setSortKeyDirection: vi.fn(),
			applyFrame: vi.fn(),
		},
		instanceResults: {
			results: {
				status: "ready",
				data: {
					items: [result],
					start: 1,
					end: 1,
					total: 1234,
					hasPrevious: false,
					hasNext: true,
				},
			},
			refreshInstanceResults: vi.fn(),
			loadPreviousInstancePage: vi.fn(),
			loadNextInstancePage: vi.fn(),
		},
	};
	return {
		workflowSelection: { ...props.workflowSelection, ...overrides.workflowSelection },
		groupingSection: { ...props.groupingSection, ...overrides.groupingSection },
		querySection: { ...props.querySection, ...overrides.querySection },
		instanceResults: { ...props.instanceResults, ...overrides.instanceResults },
	};
}

describe("WorkflowDisplayPanel", () => {
	it("renders workflow and grouping subcolumns with semantic cells", () => {
		render(<WorkflowDisplayPanel {...createProps()} />);

		expect(screen.getByRole("columnheader", { name: "Instance" })).toHaveAttribute(
			"colspan",
			"6",
		);
		expect(screen.getByRole("columnheader", { name: "Groupings" })).toHaveAttribute(
			"colspan",
			"2",
		);
		expect(screen.getByRole("columnheader", { name: "dialogue.speaker" })).toBeVisible();
		expect(screen.getByRole("columnheader", { name: "chapter.chapter_number" })).toBeVisible();
		expect(screen.getByText("A quiet promise")).toBeVisible();
		expect(screen.getByRole("button", { name: "chapter-:12–28" })).toBeVisible();
		expect(screen.getByRole("button", { name: "Label label-ab" })).toBeVisible();
	});

	it("requests application through the query section command", () => {
		const applyFrame = vi.fn();
		render(<WorkflowDisplayPanel {...createProps({ querySection: { applyFrame } })} />);

		fireEvent.click(screen.getByRole("button", { name: "Apply frame" }));

		expect(applyFrame).toHaveBeenCalledOnce();
	});

	it("preserves controlled selections and emits grouping value and page actions", () => {
		const setGroupingValueSelected = vi.fn();
		const loadNextGroupingValuesPage = vi.fn();
		render(
			<WorkflowDisplayPanel
				{...createProps({
					groupingSection: {
						setGroupingValueSelected,
						loadNextGroupingValuesPage,
					},
				})}
			/>,
		);

		const lin = screen.getByRole("checkbox", { name: /Lin/ });
		expect(lin).toBeChecked();
		fireEvent.click(screen.getByRole("checkbox", { name: /Mei/ }));
		expect(setGroupingValueSelected).toHaveBeenCalledWith(
			speakerGrouping.groupingId,
			{ type: "string", value: "Mei" },
			true,
		);
		fireEvent.click(screen.getByRole("button", { name: "Next dialogue.speaker values page" }));
		expect(loadNextGroupingValuesPage).toHaveBeenCalledWith(speakerGrouping.groupingId);
	});

	it("holds back grouping and result controls until a workflow completes", () => {
		const processingWorkflow: WorkflowResponse = {
			...workflow,
			workflowStatus: "processing",
			workflowMessage: "Building instances",
		};
		render(
			<WorkflowDisplayPanel
				{...createProps({
					workflowSelection: {
						activeWorkflow: { status: "ready", data: processingWorkflow },
					},
				})}
			/>,
		);

		expect(screen.getByText("Workflow is not ready")).toBeVisible();
		expect(screen.getByText("Building instances")).toBeVisible();
		expect(screen.queryByRole("button", { name: "Apply frame" })).not.toBeInTheDocument();
	});
});
