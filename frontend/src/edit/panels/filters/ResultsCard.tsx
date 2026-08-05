import type { InstanceQueryResult, WorkflowResponse } from "@/api/models";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardAction,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { RefreshCw } from "lucide-react";
import { DataCell, GroupDataCell } from "./DataCells";
import { ErrorBlock, groupingLabel, LoadingBlock, PageControls, shortId } from "./panelUi";
import type { ActiveGroupingState, Loadable, Page } from "./types";

function ResultsTable({
	workflow,
	activeGroupings,
	results,
	openChapter,
}: {
	workflow: WorkflowResponse;
	activeGroupings: readonly ActiveGroupingState[];
	results: Page<InstanceQueryResult>;
	openChapter?: (chapterId: string) => void;
}) {
	const fields = Object.entries(workflow.schema.fields ?? {});
	return (
		<Table>
			<TableHeader>
				<TableRow>
					<TableHead colSpan={fields.length + 1}>Instance</TableHead>
					{activeGroupings.length > 0 && (
						<TableHead colSpan={activeGroupings.length}>Groupings</TableHead>
					)}
				</TableRow>
				<TableRow>
					<TableHead>Instance ID</TableHead>
					{fields.map(([name]) => (
						<TableHead key={name}>{name}</TableHead>
					))}
					{activeGroupings.map((state) => (
						<TableHead key={state.grouping.groupingId}>
							{groupingLabel(state.grouping)}
						</TableHead>
					))}
				</TableRow>
			</TableHeader>
			<TableBody>
				{results.items.map((result) => (
					<TableRow key={result.instance.instanceId}>
						<TableCell className="font-mono">
							{shortId(result.instance.instanceId)}
						</TableCell>
						{fields.map(([name]) => (
							<TableCell key={name}>
								<DataCell
									value={result.instance.value.fields?.[name]}
									openChapter={openChapter}
								/>
							</TableCell>
						))}
						{activeGroupings.map((state) => (
							<TableCell key={state.grouping.groupingId}>
								<GroupDataCell
									value={result.groupValues[state.grouping.groupingId]}
								/>
							</TableCell>
						))}
					</TableRow>
				))}
			</TableBody>
		</Table>
	);
}

export function ResultsCard({
	workflow,
	activeGroupings,
	results,
	refreshInstanceResults,
	loadPreviousInstancePage,
	loadNextInstancePage,
	openChapter,
}: {
	workflow: WorkflowResponse;
	activeGroupings: readonly ActiveGroupingState[];
	results: Loadable<Page<InstanceQueryResult>>;
	refreshInstanceResults: () => void;
	loadPreviousInstancePage: () => void;
	loadNextInstancePage: () => void;
	openChapter?: (chapterId: string) => void;
}) {
	const description =
		results.status === "ready"
			? results.data.total === undefined
				? `${results.data.start}–${results.data.end}`
				: `${results.data.start}–${results.data.end} of ${results.data.total}`
			: "Apply the frame to load instances.";
	return (
		<Card>
			<CardHeader>
				<CardTitle>Instances</CardTitle>
				<CardDescription>{description}</CardDescription>
				<CardAction>
					<Button
						type="button"
						variant="outline"
						size="icon-sm"
						disabled={results.status !== "ready"}
						onClick={refreshInstanceResults}
						aria-label="Refresh instances"
					>
						<RefreshCw />
					</Button>
				</CardAction>
			</CardHeader>
			<CardContent className="flex flex-col gap-4">
				{results.status === "idle" && (
					<Empty className="border">
						<EmptyHeader>
							<EmptyTitle>No applied query</EmptyTitle>
							<EmptyDescription>
								Configure the frame and apply it to load instances.
							</EmptyDescription>
						</EmptyHeader>
					</Empty>
				)}
				{results.status === "loading" && <LoadingBlock />}
				{results.status === "error" && (
					<ErrorBlock title="Could not load instances" message={results.message} />
				)}
				{results.status === "ready" && results.data.items.length === 0 && (
					<Empty className="border">
						<EmptyHeader>
							<EmptyTitle>No matching instances</EmptyTitle>
							<EmptyDescription>
								Change the grouping selections or sort order and apply again.
							</EmptyDescription>
						</EmptyHeader>
					</Empty>
				)}
				{results.status === "ready" && results.data.items.length > 0 && (
					<>
						<ResultsTable
							workflow={workflow}
							activeGroupings={activeGroupings}
							results={results.data}
							openChapter={openChapter}
						/>
						<PageControls
							page={results.data}
							label="instances"
							loadPreviousPage={loadPreviousInstancePage}
							loadNextPage={loadNextInstancePage}
						/>
					</>
				)}
			</CardContent>
		</Card>
	);
}
