import type { ActiveGroupingState, WorkflowDisplayPanelProps } from "./WorkflowDisplayPanel";
import type {
	GroupingSectionModel,
	InstanceResultsModel,
	QuerySectionModel,
	WorkflowSelectionModel,
} from "../types";
import type {
	GroupingResponse,
	InstanceQueryResult,
	LabelRef,
	TextSpan,
	WorkflowResponse,
	WorkflowSummary,
} from "@/api/models";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { WorkflowDisplayPanel } from "./WorkflowDisplayPanel";

beforeAll(() => {
	Object.defineProperties(HTMLElement.prototype, {
		hasPointerCapture: { configurable: true, value: () => false },
		releasePointerCapture: { configurable: true, value: () => undefined },
		scrollIntoView: { configurable: true, value: () => undefined },
		setPointerCapture: { configurable: true, value: () => undefined },
	});
});

const workflowSummary: WorkflowSummary = {
	createdAt: "2026-08-01T00:00:00Z",
	jobId: null,
	schema: {
		kind: "schema",
		fields: {
			title: { kind: "field", type: "string" },
			rank: { kind: "field", type: "int" },
			published: { kind: "field", type: "bool" },
			excerpt: { kind: "field", type: "textSpan" },
			character: { kind: "field", type: "labelRef" },
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

const textSpanValue: TextSpan = {
	chapterId: "chapter-abcdefgh",
	chapterContentId: "content-1",
	start: 12,
	end: 28,
};

const labelRefValue: LabelRef = {
	chapterId: "chapter-abcdefgh",
	chapterContentId: "content-1",
	labelDataId: "label-data-1",
	labelGroupId: "label-group-1",
	labelId: "label-abcdefgh",
};

const result: InstanceQueryResult = {
	instance: {
		instanceId: "instance-12345678",
		workflowId: workflow.workflowId,
		value: {
			kind: "object",
			fields: {
				title: { kind: "value", type: "string", value: "A quiet promise" },
				rank: { kind: "value", type: "int", value: 7 },
				published: { kind: "value", type: "bool", value: true },
				excerpt: {
					kind: "value",
					type: "textSpan",
					value: textSpanValue,
				},
				character: {
					kind: "value",
					type: "labelRef",
					value: labelRefValue,
				},
			},
		},
	},
	groupValues: {
		"grouping-speaker": { kind: "value", type: "string", value: "Lin" },
		"grouping-chapter": { kind: "value", type: "int", value: 4 },
	},
};

function activeGroupingStates() {
	const speaker: ActiveGroupingState = {
		grouping: speakerGrouping,
		search: "",
		selectedValues: [{ kind: "value", type: "string", value: "Lin" }],
		values: {
			status: "ready",
			data: {
				items: [
					{ value: { kind: "value", type: "string", value: "Lin" }, count: 18 },
					{ value: { kind: "value", type: "string", value: "Mei" }, count: 12 },
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
				items: [{ value: { kind: "value", type: "int", value: 4 }, count: 30 }],
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
			refreshWorkflowList: vi.fn(),
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
			commitInstanceField: vi.fn(),
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
	async function selectGrouping(groupingName: string) {
		const trigger = screen.getByRole("combobox", { name: "Add grouping" });
		fireEvent.pointerDown(trigger, { button: 0, ctrlKey: false, pointerType: "mouse" });
		fireEvent.click(await screen.findByRole("option", { name: groupingName }));
	}

	it("refreshes only the workflow catalog on command", () => {
		const props = createProps();
		render(<WorkflowDisplayPanel {...props} />);

		fireEvent.click(screen.getByRole("button", { name: "Refresh workflows" }));

		expect(props.workflowSelection.refreshWorkflowList).toHaveBeenCalledOnce();
		expect(props.instanceResults.refreshInstanceResults).not.toHaveBeenCalled();
	});

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

	it("opens text references on double-click and keeps metadata behind info buttons", () => {
		const gotoText = vi.fn();
		render(
			<WorkflowDisplayPanel {...createProps()} />,
		);

		fireEvent.click(screen.getByRole("button", { name: "chapter-:12–28" }), {
			detail: 1,
		});
		expect(gotoText).not.toHaveBeenCalled();

		fireEvent.doubleClick(screen.getByRole("button", { name: "chapter-:12–28" }));
		expect(gotoText).toHaveBeenCalledWith({
			type: "textSpan",
			value: textSpanValue,
		});

		fireEvent.doubleClick(screen.getByRole("button", { name: "Label label-ab" }));
		expect(gotoText).toHaveBeenLastCalledWith({
			type: "labelRef",
			value: labelRefValue,
		});

		fireEvent.click(screen.getByRole("button", { name: "Text span info" }));
		expect(screen.getByText("content-1")).toBeVisible();
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
		const meiValue = screen.getByText("Mei");
		const meiCount = screen.getByText("12");
		expect(meiValue.parentElement).toHaveClass("select-text");
		expect(meiCount).toHaveClass("select-text");
		fireEvent.click(meiValue);
		expect(setGroupingValueSelected).not.toHaveBeenCalled();
		fireEvent.click(screen.getByRole("checkbox", { name: /Mei/ }));
		expect(setGroupingValueSelected).toHaveBeenCalledWith(
			speakerGrouping.groupingId,
			{ kind: "value", type: "string", value: "Mei" },
			true,
		);
		fireEvent.click(screen.getByRole("button", { name: "Next dialogue.speaker values page" }));
		expect(loadNextGroupingValuesPage).toHaveBeenCalledWith(speakerGrouping.groupingId);
	});

	it("allows a removed grouping to be selected again", async () => {
		const activateGrouping = vi.fn();
		const deactivateGrouping = vi.fn();
		const inactiveGroupings = new Map<string, ActiveGroupingState>();
		const speakerGroupingOnly = new Map(
			[...activeGroupingStates()].filter(
				([groupingId]) => groupingId === speakerGrouping.groupingId,
			),
		);
		const { rerender } = render(
			<WorkflowDisplayPanel
				{...createProps({
					groupingSection: {
						activeGroupings: inactiveGroupings,
						activateGrouping,
						deactivateGrouping,
					},
				})}
			/>,
		);

		await selectGrouping("dialogue.speaker");
		expect(activateGrouping).toHaveBeenCalledWith(speakerGrouping.groupingId);

		rerender(
			<WorkflowDisplayPanel
				{...createProps({
					groupingSection: {
						activeGroupings: speakerGroupingOnly,
						activateGrouping,
						deactivateGrouping,
					},
				})}
			/>,
		);
		fireEvent.click(screen.getByRole("button", { name: "Remove dialogue.speaker" }));
		expect(deactivateGrouping).toHaveBeenCalledWith(speakerGrouping.groupingId);

		rerender(
			<WorkflowDisplayPanel
				{...createProps({
					groupingSection: {
						activeGroupings: inactiveGroupings,
						activateGrouping,
						deactivateGrouping,
					},
				})}
			/>,
		);
		await selectGrouping("dialogue.speaker");
		expect(activateGrouping).toHaveBeenCalledTimes(2);
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
