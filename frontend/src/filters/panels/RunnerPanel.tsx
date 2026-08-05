import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { FilterRunnerForm } from "../components/runnerForms/FilterRunnerForm";
import { GroupRunnerForm } from "../components/runnerForms/GroupRunnerForm";
import { LabelSourceRunnerForm } from "../components/runnerForms/LabelSourceRunnerForm";
import { MapRunnerForm } from "../components/runnerForms/MapRunnerForm";
import type { RunnerOperation, RunnerPanelModel } from "../types";

function isRunnerOperation(value: string): value is RunnerOperation {
	return value === "labelSource" || value === "map" || value === "filter" || value === "group";
}

export function RunnerPanel(props: RunnerPanelModel) {
	return (
		<section className="flex min-w-0 flex-col gap-4" aria-labelledby="runner-panel-title">
			<Card>
				<CardHeader>
					<CardTitle id="runner-panel-title">Workflow runners</CardTitle>
					<CardDescription>
						Choose an operation, select its inputs, and enqueue it for the filters
						worker.
					</CardDescription>
				</CardHeader>
				<CardContent>
					<ToggleGroup
						type="single"
						variant="outline"
						spacing={0}
						value={props.activeRunnerOperation}
						onValueChange={(value) => {
							if (isRunnerOperation(value)) props.selectRunnerOperation(value);
						}}
						className="w-full flex-wrap"
						aria-label="Runner operation"
					>
						<ToggleGroupItem value="labelSource" className="min-w-28 flex-1">
							Label source
						</ToggleGroupItem>
						<ToggleGroupItem value="map" className="min-w-28 flex-1">
							Map
						</ToggleGroupItem>
						<ToggleGroupItem value="filter" className="min-w-28 flex-1">
							Filter
						</ToggleGroupItem>
						<ToggleGroupItem value="group" className="min-w-28 flex-1">
							Group
						</ToggleGroupItem>
					</ToggleGroup>
				</CardContent>
			</Card>

			{props.activeRunnerOperation === "labelSource" && (
				<LabelSourceRunnerForm {...props.labelSourceForm} />
			)}
			{props.activeRunnerOperation === "map" && <MapRunnerForm {...props.mapForm} />}
			{props.activeRunnerOperation === "filter" && <FilterRunnerForm {...props.filterForm} />}
			{props.activeRunnerOperation === "group" && <GroupRunnerForm {...props.groupForm} />}
		</section>
	);
}
