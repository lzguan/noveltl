import {
	readGroupingValuesFiltersGroupingsGroupingIdValuesGet,
	readInstancesAdvancedFiltersInstancesQueryPost,
	readWorkflowFiltersWorkflowsWorkflowIdGet,
	readWorkflowGroupingsFiltersWorkflowsWorkflowIdGroupingsGet,
	readWorkflowsFiltersWorkflowsGet,
	updateFilterInstance,
} from "@/api/endpoints/filters/filters";
import type {
	Frame,
	GroupingResponse,
	InstanceQueryResult,
	WorkflowResponse,
	WorkflowSummary,
} from "@/api/models";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useFrameDraft } from "./useFrameDraft";
import { useInstanceResults } from "./useInstanceResults";
import { useWorkflowGroupings } from "./useWorkflowGroupings";
import { useWorkflowSelection } from "./useWorkflowSelection";
import { buildWorkflowFrame } from "./useWorkflowViewer";
import type { ActiveGroupingState } from "./useWorkflowGroupings";

vi.mock("@/api/endpoints/filters/filters", () => ({
	readGroupingFiltersGroupingsGroupingIdGet: vi.fn(),
	readGroupingValuesFiltersGroupingsGroupingIdValuesGet: vi.fn(),
	readInstancesAdvancedFiltersInstancesQueryPost: vi.fn(),
	readWorkflowFiltersWorkflowsWorkflowIdGet: vi.fn(),
	readWorkflowGroupingsFiltersWorkflowsWorkflowIdGroupingsGet: vi.fn(),
	readWorkflowsFiltersWorkflowsGet: vi.fn(),
	updateFilterInstance: vi.fn(),
}));

const workflowSummary: WorkflowSummary = {
	createdAt: "2026-08-01T00:00:00Z",
	jobId: null,
	schema: {
		kind: "schema",
		fields: {
			name: { kind: "field", type: "string" },
			rank: { kind: "field", type: "int" },
		},
	},
	updatedAt: "2026-08-01T00:00:00Z",
	useCase: "advanced",
	workflowId: "workflow-1",
	workflowMessage: null,
	workflowName: "Candidates",
	workflowStatus: "complete",
};

const workflow: WorkflowResponse = {
	...workflowSummary,
	instanceCount: 80,
	labelGroupIds: [],
	novelIds: ["novel-1"],
};

const grouping: GroupingResponse = {
	assignmentCount: 80,
	createdAt: "2026-08-01T00:00:00Z",
	functionDefinition: {
		functionDefinitionId: "function-1",
		functionName: "speaker",
		namespace: "dialogue",
	},
	groupingId: "grouping-1",
	groupingMessage: null,
	groupingStatus: "complete",
	jobId: "job-1",
	outputType: "string",
	updatedAt: "2026-08-01T00:00:00Z",
	workflowId: workflow.workflowId,
};

const frame: Frame = {
	workflowId: workflow.workflowId,
	groupFilters: [],
	sortKeys: [],
};

function instanceResult(index: number): InstanceQueryResult {
	return {
		groupValues: {},
		instance: {
			instanceId: `instance-${index}`,
			workflowId: workflow.workflowId,
			value: {
				kind: "object",
				fields: { rank: { kind: "value", type: "int", value: index } },
			},
		},
	};
}

describe("workflow viewer hooks", () => {
	beforeEach(() => vi.clearAllMocks());

	it("loads the novel workflow catalog and selected workflow metadata", async () => {
		vi.mocked(readWorkflowsFiltersWorkflowsGet).mockResolvedValue({
			status: 200,
			data: [workflowSummary],
			headers: new Headers(),
		});
		vi.mocked(readWorkflowFiltersWorkflowsWorkflowIdGet).mockResolvedValue({
			status: 200,
			data: workflow,
			headers: new Headers(),
		});
		vi.mocked(readWorkflowGroupingsFiltersWorkflowsWorkflowIdGroupingsGet).mockResolvedValue({
			status: 200,
			data: [],
			headers: new Headers(),
		});

		const { result } = renderHook(() => useWorkflowSelection("novel-1"));
		await waitFor(() => expect(result.current.workflows.status).toBe("ready"));
		act(() => result.current.selectWorkflow(workflow.workflowId));
		await waitFor(() => expect(result.current.activeWorkflow.status).toBe("ready"));

		expect(readWorkflowsFiltersWorkflowsGet).toHaveBeenCalledWith(
			{ novelId: "novel-1", limit: 100 },
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);
		expect(result.current.availableGroupings).toEqual({ status: "ready", data: [] });

		act(() => result.current.refreshWorkflowList());
		await waitFor(() => expect(readWorkflowsFiltersWorkflowsGet).toHaveBeenCalledTimes(2));
		expect(result.current.activeWorkflowId).toBe(workflow.workflowId);
		expect(readWorkflowFiltersWorkflowsWorkflowIdGet).toHaveBeenCalledOnce();
	});

	it("reloads workflow metadata when the selected workflow is selected again", async () => {
		const processingWorkflow: WorkflowResponse = {
			...workflow,
			workflowStatus: "processing",
		};
		vi.mocked(readWorkflowsFiltersWorkflowsGet).mockResolvedValue({
			status: 200,
			data: [workflowSummary],
			headers: new Headers(),
		});
		vi.mocked(readWorkflowFiltersWorkflowsWorkflowIdGet)
			.mockResolvedValueOnce({
				status: 200,
				data: processingWorkflow,
				headers: new Headers(),
			})
			.mockResolvedValueOnce({
				status: 200,
				data: workflow,
				headers: new Headers(),
			});
		vi.mocked(readWorkflowGroupingsFiltersWorkflowsWorkflowIdGroupingsGet).mockResolvedValue({
			status: 200,
			data: [],
			headers: new Headers(),
		});

		const { result } = renderHook(() => useWorkflowSelection("novel-1"));
		await waitFor(() => expect(result.current.workflows.status).toBe("ready"));

		act(() => result.current.selectWorkflow(workflow.workflowId));
		await waitFor(() => {
			expect(result.current.activeWorkflow).toEqual({
				status: "ready",
				data: processingWorkflow,
			});
		});

		act(() => result.current.selectWorkflow(workflow.workflowId));
		await waitFor(() => {
			expect(readWorkflowFiltersWorkflowsWorkflowIdGet).toHaveBeenCalledTimes(2);
			expect(result.current.activeWorkflow).toEqual({ status: "ready", data: workflow });
		});
		expect(result.current.availableGroupings).toEqual({ status: "ready", data: [] });
	});

	it("owns grouping activation, selection, search, and value pagination", async () => {
		type GroupingValuesResponse = Awaited<
			ReturnType<typeof readGroupingValuesFiltersGroupingsGroupingIdValuesGet>
		>;
		const firstPage = Array.from({ length: 50 }, (_, index) => ({
			value: { kind: "value" as const, type: "string" as const, value: `Value ${index}` },
			count: 4,
		}));
		let resolveNextPage: (response: GroupingValuesResponse) => void = () => undefined;
		const nextPage = new Promise<GroupingValuesResponse>((resolve) => {
			resolveNextPage = resolve;
		});
		vi.mocked(readGroupingValuesFiltersGroupingsGroupingIdValuesGet)
			.mockResolvedValueOnce({ status: 200, data: firstPage, headers: new Headers() })
			.mockReturnValueOnce(nextPage);
		const { result } = renderHook(() =>
			useWorkflowGroupings({ status: "ready", data: [grouping] }),
		);

		act(() => result.current.activateGrouping(grouping.groupingId));
		await waitFor(() =>
			expect(result.current.activeGroupings.get(grouping.groupingId)?.values.status).toBe(
				"ready",
			),
		);
		act(() =>
			result.current.setGroupingValueSelected(grouping.groupingId, firstPage[0].value, true),
		);
		expect(result.current.activeGroupings.get(grouping.groupingId)?.selectedValues).toEqual([
			firstPage[0].value,
		]);

		act(() => result.current.loadNextGroupingValuesPage(grouping.groupingId));
		expect(result.current.activeGroupings.get(grouping.groupingId)?.values).toEqual({
			status: "ready",
			data: {
				items: firstPage,
				start: 1,
				end: 50,
				hasPrevious: false,
				hasNext: true,
			},
		});
		expect(readGroupingValuesFiltersGroupingsGroupingIdValuesGet).toHaveBeenLastCalledWith(
			grouping.groupingId,
			{ search: undefined, limit: 50, offset: 50 },
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);

		resolveNextPage({
			status: 200,
			data: [{ value: { kind: "value", type: "string", value: "Next" }, count: 2 }],
			headers: new Headers(),
		});
		await waitFor(() => {
			const values = result.current.activeGroupings.get(grouping.groupingId)?.values;
			expect(values?.status).toBe("ready");
			if (values?.status === "ready") expect(values.data.start).toBe(51);
		});
	});

	it("exposes sort-key-specific frame draft commands", () => {
		const { result } = renderHook(() => useFrameDraft(workflow));

		act(() => result.current.addSortKey());
		expect(result.current.sortKeys).toEqual([{ fieldName: "name", direction: "asc" }]);
		act(() => result.current.setSortKeyField(0, "rank"));
		act(() => result.current.setSortKeyDirection(0, "desc"));
		expect(result.current.sortKeys).toEqual([{ fieldName: "rank", direction: "desc" }]);
		act(() => result.current.removeSortKey(0));
		expect(result.current.sortKeys).toEqual([]);
	});

	it("retains applied frame and cursor history across instance pages", async () => {
		vi.mocked(readInstancesAdvancedFiltersInstancesQueryPost)
			.mockResolvedValueOnce({
				status: 200,
				data: Array.from({ length: 50 }, (_, index) => instanceResult(index)),
				headers: new Headers(),
			})
			.mockResolvedValueOnce({
				status: 200,
				data: [instanceResult(50)],
				headers: new Headers(),
			});
		const { result } = renderHook(() => useInstanceResults());

		act(() => result.current.applyFrame(frame));
		await waitFor(() => expect(result.current.results.status).toBe("ready"));
		act(() => result.current.loadNextInstancePage());
		await waitFor(() => {
			expect(result.current.results.status).toBe("ready");
			if (result.current.results.status === "ready")
				expect(result.current.results.data.start).toBe(51);
		});

		expect(readInstancesAdvancedFiltersInstancesQueryPost).toHaveBeenLastCalledWith(
			{ frame, cursor: "instance-49", limit: 50 },
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);
	});

	it("updates one instance field and replaces the cached instance", async () => {
		const original = instanceResult(1);
		const updatedInstance = {
			...original.instance,
			value: {
				...original.instance.value,
				fields: {
					...original.instance.value.fields,
					rank: { kind: "value" as const, type: "int" as const, value: 9 },
				},
			},
		};
		vi.mocked(readInstancesAdvancedFiltersInstancesQueryPost).mockResolvedValue({
			status: 200,
			data: [original],
			headers: new Headers(),
		});
		vi.mocked(updateFilterInstance).mockResolvedValue({
			status: 200,
			data: updatedInstance,
			headers: new Headers(),
		});
		const { result } = renderHook(() => useInstanceResults());
		act(() => result.current.applyFrame(frame));
		await waitFor(() => expect(result.current.results.status).toBe("ready"));

		await act(() =>
			result.current.commitInstanceField("instance-1", "rank", {
				kind: "value",
				type: "int",
				value: 9,
			}),
		);

		expect(updateFilterInstance).toHaveBeenCalledWith("instance-1", {
			fields: { rank: { kind: "value", type: "int", value: 9 } },
		});
		expect(result.current.results).toEqual({
			status: "ready",
			data: {
				items: [{ ...original, instance: updatedInstance }],
				start: 1,
				end: 1,
				hasPrevious: false,
				hasNext: false,
			},
		});
	});

	it("builds a frame from active grouping projections and draft sort keys", () => {
		const activeGroupings: ReadonlyMap<string, ActiveGroupingState> = new Map([
			[
				grouping.groupingId,
				{
					grouping,
					search: "",
					selectedValues: [{ kind: "value", type: "string", value: "Lin" }],
					values: { status: "idle" },
				},
			],
		]);

		expect(
			buildWorkflowFrame(workflow, activeGroupings, [
				{ fieldName: "rank", direction: "desc" },
			]),
		).toEqual({
			workflowId: workflow.workflowId,
			groupFilters: [
				{
					groupingId: grouping.groupingId,
					values: [{ kind: "value", type: "string", value: "Lin" }],
				},
			],
			sortKeys: [{ fieldName: "rank", direction: "desc" }],
		});
	});
});
