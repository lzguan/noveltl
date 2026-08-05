import type { GroupData, GroupingResponse } from "@/api/models";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardAction,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Search, Trash2 } from "lucide-react";
import { GroupDataCell } from "./DataCells";
import { ErrorBlock, groupingLabel, LoadingBlock, PageControls, statusVariant } from "./panelUi";
import type { ActiveGroupingState, Loadable } from "../types";

function dataKey(value: GroupData) {
	return `${value.type}:${String(value.value)}`;
}

function GroupValueRows({
	state,
	setGroupingValueSelected,
}: {
	state: ActiveGroupingState;
	setGroupingValueSelected: (value: GroupData, selected: boolean) => void;
}) {
	if (state.values.status === "loading" || state.values.status === "idle")
		return <LoadingBlock />;
	if (state.values.status === "error")
		return <ErrorBlock title="Could not load grouping values" message={state.values.message} />;
	if (state.values.data.items.length === 0) {
		return (
			<Empty className="border py-8">
				<EmptyHeader>
					<EmptyTitle>No grouping values</EmptyTitle>
					<EmptyDescription>Try another search.</EmptyDescription>
				</EmptyHeader>
			</Empty>
		);
	}
	const selectedKeys = new Set(state.selectedValues.map(dataKey));
	return (
		<FieldGroup data-slot="checkbox-group">
			{state.values.data.items.map((row) => {
				const key = dataKey(row.value);
				const id = `${state.grouping.groupingId}-${key}`;
				return (
					<Field orientation="horizontal" key={key}>
						<Checkbox
							id={id}
							checked={selectedKeys.has(key)}
							onCheckedChange={(checked) =>
								setGroupingValueSelected(row.value, checked === true)
							}
						/>
						<FieldLabel htmlFor={id}>
							<span className="min-w-0 flex-1 truncate">
								<GroupDataCell value={row.value} />
							</span>
							<Badge variant="secondary">{row.count}</Badge>
						</FieldLabel>
					</Field>
				);
			})}
		</FieldGroup>
	);
}

function ActiveGroupingCard({
	state,
	deactivateGrouping,
	setGroupingValueSearchText,
	setGroupingValueSelected,
	loadPreviousGroupingValuesPage,
	loadNextGroupingValuesPage,
}: {
	state: ActiveGroupingState;
	deactivateGrouping: () => void;
	setGroupingValueSearchText: (searchText: string) => void;
	setGroupingValueSelected: (value: GroupData, selected: boolean) => void;
	loadPreviousGroupingValuesPage: () => void;
	loadNextGroupingValuesPage: () => void;
}) {
	return (
		<Card size="sm">
			<CardHeader>
				<CardTitle>{groupingLabel(state.grouping)}</CardTitle>
				<CardDescription>
					{state.selectedValues.length} selected · empty selection projects without
					filtering
				</CardDescription>
				<CardAction className="flex items-center gap-1">
					<Badge variant={statusVariant(state.grouping.groupingStatus)}>
						{state.grouping.outputType}
					</Badge>
					<Button
						type="button"
						variant="ghost"
						size="icon-xs"
						onClick={deactivateGrouping}
						aria-label={`Remove ${groupingLabel(state.grouping)}`}
					>
						<Trash2 />
					</Button>
				</CardAction>
			</CardHeader>
			<CardContent className="flex flex-col gap-4">
				{state.grouping.outputType === "string" && (
					<Field>
						<FieldLabel
							htmlFor={`search-${state.grouping.groupingId}`}
							className="sr-only"
						>
							Search {groupingLabel(state.grouping)} values
						</FieldLabel>
						<div className="relative">
							<Search className="absolute top-2.5 left-2.5 size-4 text-muted-foreground" />
							<Input
								id={`search-${state.grouping.groupingId}`}
								className="pl-8"
								value={state.search}
								onChange={(event) => setGroupingValueSearchText(event.target.value)}
								placeholder="Search values"
							/>
						</div>
					</Field>
				)}
				{state.values.status === "ready" ? (
					<div className="flex flex-col gap-3">
						<GroupValueRows
							state={state}
							setGroupingValueSelected={setGroupingValueSelected}
						/>
						<PageControls
							page={state.values.data}
							label={`${groupingLabel(state.grouping)} values`}
							loadPreviousPage={loadPreviousGroupingValuesPage}
							loadNextPage={loadNextGroupingValuesPage}
						/>
					</div>
				) : (
					<GroupValueRows
						state={state}
						setGroupingValueSelected={setGroupingValueSelected}
					/>
				)}
			</CardContent>
		</Card>
	);
}

export function GroupingSection({
	availableGroupings,
	activeGroupings,
	activateGrouping,
	deactivateGrouping,
	setGroupingValueSearchText,
	setGroupingValueSelected,
	loadPreviousGroupingValuesPage,
	loadNextGroupingValuesPage,
}: {
	availableGroupings: Loadable<readonly GroupingResponse[]>;
	activeGroupings: readonly ActiveGroupingState[];
	activateGrouping: (groupingId: string) => void;
	deactivateGrouping: (groupingId: string) => void;
	setGroupingValueSearchText: (groupingId: string, searchText: string) => void;
	setGroupingValueSelected: (groupingId: string, value: GroupData, selected: boolean) => void;
	loadPreviousGroupingValuesPage: (groupingId: string) => void;
	loadNextGroupingValuesPage: (groupingId: string) => void;
}) {
	const activeIds = new Set(activeGroupings.map((state) => state.grouping.groupingId));
	const available =
		availableGroupings.status === "ready"
			? availableGroupings.data.filter((grouping) => !activeIds.has(grouping.groupingId))
			: [];
	return (
		<Card>
			<CardHeader>
				<CardTitle>Groupings</CardTitle>
				<CardDescription>
					Active groupings are projected as table columns. Selecting values also filters
					rows.
				</CardDescription>
			</CardHeader>
			<CardContent className="flex flex-col gap-4">
				<Field>
					<FieldLabel htmlFor="add-grouping">Add grouping</FieldLabel>
					<Select
						disabled={availableGroupings.status !== "ready" || available.length === 0}
						onValueChange={activateGrouping}
					>
						<SelectTrigger id="add-grouping" className="w-full">
							<SelectValue
								placeholder={
									available.length === 0
										? "No groupings available"
										: "Choose a grouping"
								}
							/>
						</SelectTrigger>
						<SelectContent>
							<SelectGroup>
								{available.map((grouping) => (
									<SelectItem
										key={grouping.groupingId}
										value={grouping.groupingId}
									>
										{groupingLabel(grouping)}
									</SelectItem>
								))}
							</SelectGroup>
						</SelectContent>
					</Select>
				</Field>
				{availableGroupings.status === "error" && (
					<ErrorBlock
						title="Could not load groupings"
						message={availableGroupings.message}
					/>
				)}
				{activeGroupings.length === 0 ? (
					<Empty className="border py-8">
						<EmptyHeader>
							<EmptyTitle>No active groupings</EmptyTitle>
							<EmptyDescription>
								Results will include workflow fields only.
							</EmptyDescription>
						</EmptyHeader>
					</Empty>
				) : (
					activeGroupings.map((state) => (
						<ActiveGroupingCard
							key={state.grouping.groupingId}
							state={state}
							deactivateGrouping={() => deactivateGrouping(state.grouping.groupingId)}
							setGroupingValueSearchText={(searchText) =>
								setGroupingValueSearchText(state.grouping.groupingId, searchText)
							}
							setGroupingValueSelected={(value, selected) =>
								setGroupingValueSelected(state.grouping.groupingId, value, selected)
							}
							loadPreviousGroupingValuesPage={() =>
								loadPreviousGroupingValuesPage(state.grouping.groupingId)
							}
							loadNextGroupingValuesPage={() =>
								loadNextGroupingValuesPage(state.grouping.groupingId)
							}
						/>
					))
				)}
			</CardContent>
		</Card>
	);
}
