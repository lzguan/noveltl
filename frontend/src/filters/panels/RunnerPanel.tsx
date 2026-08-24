import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { FilterRunnerForm } from "../components/runnerForms/FilterRunnerForm";
import { AnnotationRunnerForm } from "../components/runnerForms/AnnotationRunnerForm";
import { GroupRunnerForm } from "../components/runnerForms/GroupRunnerForm";
import { LabelSourceRunnerForm } from "../components/runnerForms/LabelSourceRunnerForm";
import { MapRunnerForm } from "../components/runnerForms/MapRunnerForm";
import { useState } from "react";

function isRunnerOperation(
	value: string,
): value is "labelSource" | "annotation" | "map" | "filter" | "group" {
	return (
		value === "labelSource" ||
		value === "annotation" ||
		value === "map" ||
		value === "filter" ||
		value === "group"
	);
}

export function RunnerPanel({ novelId, enabled }: { novelId: string; enabled: boolean }) {
	const [activeRunnerOperation, setActiveRunnerOperation] = useState<
		"labelSource" | "annotation" | "map" | "filter" | "group"
	>("labelSource");

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
						value={activeRunnerOperation}
						onValueChange={(value) => {
							if (isRunnerOperation(value)) setActiveRunnerOperation(value);
						}}
						className="w-full flex-wrap"
						aria-label="Runner operation"
					>
						<ToggleGroupItem value="labelSource" className="min-w-28 flex-1">
							Label source
						</ToggleGroupItem>
						<ToggleGroupItem value="annotation" className="min-w-28 flex-1">
							Annotation
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

			<div hidden={activeRunnerOperation !== "labelSource"}>
				<LabelSourceRunnerForm
					novelId={novelId}
					enabled={enabled && activeRunnerOperation === "labelSource"}
				/>
			</div>
			<div hidden={activeRunnerOperation !== "annotation"}>
				<AnnotationRunnerForm
					novelId={novelId}
					enabled={enabled && activeRunnerOperation === "annotation"}
				/>
			</div>
			<div hidden={activeRunnerOperation !== "map"}>
				<MapRunnerForm
					novelId={novelId}
					enabled={enabled && activeRunnerOperation === "map"}
				/>
			</div>
			<div hidden={activeRunnerOperation !== "filter"}>
				<FilterRunnerForm
					novelId={novelId}
					enabled={enabled && activeRunnerOperation === "filter"}
				/>
			</div>
			<div hidden={activeRunnerOperation !== "group"}>
				<GroupRunnerForm
					novelId={novelId}
					enabled={enabled && activeRunnerOperation === "group"}
				/>
			</div>
		</section>
	);
}
