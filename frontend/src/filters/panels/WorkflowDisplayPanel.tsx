import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
	Card,
	CardAction,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import {
	Empty,
	EmptyDescription,
	EmptyHeader,
	EmptyMedia,
	EmptyTitle,
} from "@/components/ui/empty";
import { Database } from "lucide-react";
import { GroupingSection } from "../components/GroupingSection";
import { ErrorBlock, LoadingBlock, shortId, statusVariant } from "../components/panelUi";
import { QueryCard } from "../components/QueryCard";
import { ResultsCard } from "../components/ResultsCard";
import type { useWorkflowViewer } from "../hooks/useWorkflowViewer";
import { WorkflowPicker } from "../components/WorkflowPicker";
import type { CCServId, CServId } from "@/edit/controller/types/idTypes";

export function WorkflowDisplayPanel(
	props: ReturnType<typeof useWorkflowViewer> & {
		gotoText?: (
			chapterId: CServId,
			reference: { start: number; end: number; ccServId: CCServId },
		) => void;
	},
) {
	const { workflowSelection, groupingSection, querySection, instanceResults } = props;
	const activeGroupings = [...groupingSection.activeGroupings.values()];
	const workflow =
		workflowSelection.activeWorkflow.status === "ready"
			? workflowSelection.activeWorkflow.data
			: null;

	return (
		<section className="flex min-w-0 flex-col gap-4" aria-labelledby="workflow-display-title">
			<Card>
				<CardHeader>
					<CardTitle id="workflow-display-title">Workflow instances</CardTitle>
					<CardDescription>
						Select a workflow, project groupings, and apply a frame.
					</CardDescription>
				</CardHeader>
				<CardContent>
					<WorkflowPicker
						workflows={workflowSelection.workflows}
						searchText={workflowSelection.searchText}
						activeWorkflowId={workflowSelection.activeWorkflowId}
						setWorkflowSearchText={workflowSelection.setWorkflowSearchText}
						selectWorkflow={workflowSelection.selectWorkflow}
						refreshWorkflowList={workflowSelection.refreshWorkflowList}
					/>
				</CardContent>
			</Card>
			{workflowSelection.activeWorkflowId === null && (
				<Empty className="border">
					<EmptyMedia variant="icon">
						<Database />
					</EmptyMedia>
					<EmptyHeader>
						<EmptyTitle>Select a workflow</EmptyTitle>
						<EmptyDescription>
							Workflow details and instances will appear here.
						</EmptyDescription>
					</EmptyHeader>
				</Empty>
			)}
			{workflowSelection.activeWorkflowId !== null &&
				(workflowSelection.activeWorkflow.status === "loading" ||
					workflowSelection.activeWorkflow.status === "idle") && <LoadingBlock />}
			{workflowSelection.activeWorkflow.status === "error" && (
				<ErrorBlock
					title="Could not load workflow"
					message={workflowSelection.activeWorkflow.message}
				/>
			)}
			{workflow && (
				<>
					<Card size="sm">
						<CardHeader>
							<CardTitle>
								{workflow.workflowName ||
									`Untitled workflow · ${shortId(workflow.workflowId)}`}
							</CardTitle>
							<CardDescription>
								{workflow.instanceCount.toLocaleString()} instances ·{" "}
								{workflow.useCase}
							</CardDescription>
							<CardAction>
								<Badge variant={statusVariant(workflow.workflowStatus)}>
									{workflow.workflowStatus}
								</Badge>
							</CardAction>
						</CardHeader>
					</Card>
					{workflow.workflowStatus !== "complete" ? (
						<Alert
							variant={
								workflow.workflowStatus === "failed" ? "destructive" : "default"
							}
						>
							<AlertTitle>
								{workflow.workflowStatus === "failed"
									? "Workflow failed"
									: "Workflow is not ready"}
							</AlertTitle>
							<AlertDescription>
								{workflow.workflowMessage ||
									"Grouping and instance controls become available when processing completes."}
							</AlertDescription>
						</Alert>
					) : (
						<>
							<GroupingSection
								availableGroupings={groupingSection.availableGroupings}
								activeGroupings={activeGroupings}
								activateGrouping={groupingSection.activateGrouping}
								deactivateGrouping={groupingSection.deactivateGrouping}
								setGroupingValueSearchText={
									groupingSection.setGroupingValueSearchText
								}
								setGroupingValueSelected={groupingSection.setGroupingValueSelected}
								loadPreviousGroupingValuesPage={
									groupingSection.loadPreviousGroupingValuesPage
								}
								loadNextGroupingValuesPage={
									groupingSection.loadNextGroupingValuesPage
								}
							/>
							<QueryCard
								workflow={workflow}
								sortKeys={querySection.sortKeys}
								queryStatus={querySection.queryStatus}
								addSortKey={querySection.addSortKey}
								removeSortKey={querySection.removeSortKey}
								setSortKeyField={querySection.setSortKeyField}
								setSortKeyDirection={querySection.setSortKeyDirection}
								applyFrame={querySection.applyFrame}
							/>
							<ResultsCard
								workflow={workflow}
								activeGroupings={activeGroupings}
								results={instanceResults.results}
								commitInstanceField={instanceResults.commitInstanceField}
								refreshInstanceResults={instanceResults.refreshInstanceResults}
								loadPreviousInstancePage={instanceResults.loadPreviousInstancePage}
								loadNextInstancePage={instanceResults.loadNextInstancePage}
								gotoText={props.gotoText}
							/>
						</>
					)}
				</>
			)}
		</section>
	);
}

export type { ActiveGroupingState } from "../hooks/useWorkflowGroupings";
export type { Loadable } from "../../lib/loadable";
