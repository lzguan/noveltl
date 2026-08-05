import type { SortDirection, SortKey, WorkflowResponse } from "@/api/models";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Field, FieldGroup, FieldLegend, FieldSet } from "@/components/ui/field";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Plus, Trash2 } from "lucide-react";
import { ErrorBlock } from "./panelUi";
import type { QueryStatus } from "./types";

function sortableFields(workflow: WorkflowResponse) {
	return Object.entries(workflow.schema.fields ?? {}).filter((entry) => {
		const type = entry[1].type;
		return type === "string" || type === "int" || type === "float" || type === "bool";
	});
}

function SortControls({
	workflow,
	sortKeys,
	addSortKey,
	removeSortKey,
	setSortKeyField,
	setSortKeyDirection,
}: {
	workflow: WorkflowResponse;
	sortKeys: readonly SortKey[];
	addSortKey: () => void;
	removeSortKey: (index: number) => void;
	setSortKeyField: (index: number, fieldName: string) => void;
	setSortKeyDirection: (index: number, direction: SortDirection) => void;
}) {
	const fields = sortableFields(workflow);
	return (
		<FieldSet>
			<FieldLegend variant="label">Sort order</FieldLegend>
			<FieldGroup>
				{sortKeys.map((sortKey, index) => (
					<Field orientation="responsive" key={`${index}-${sortKey.fieldName}`}>
						<Select
							value={sortKey.fieldName}
							onValueChange={(fieldName) => setSortKeyField(index, fieldName)}
						>
							<SelectTrigger
								aria-label={`Sort field ${index + 1}`}
								className="min-w-40"
							>
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								<SelectGroup>
									{fields.map(([fieldName]) => (
										<SelectItem value={fieldName} key={fieldName}>
											{fieldName}
										</SelectItem>
									))}
								</SelectGroup>
							</SelectContent>
						</Select>
						<Select
							value={sortKey.direction}
							onValueChange={(direction: SortDirection) =>
								setSortKeyDirection(index, direction)
							}
						>
							<SelectTrigger aria-label={`Sort direction ${index + 1}`}>
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								<SelectGroup>
									<SelectItem value="asc">Ascending</SelectItem>
									<SelectItem value="desc">Descending</SelectItem>
								</SelectGroup>
							</SelectContent>
						</Select>
						<Button
							type="button"
							variant="ghost"
							size="icon-sm"
							onClick={() => removeSortKey(index)}
							aria-label={`Remove sort key ${index + 1}`}
						>
							<Trash2 />
						</Button>
					</Field>
				))}
			</FieldGroup>
			<Button
				type="button"
				variant="outline"
				size="sm"
				disabled={sortKeys.length >= 3 || fields.length === 0}
				onClick={addSortKey}
			>
				<Plus data-icon="inline-start" /> Add sort key
			</Button>
		</FieldSet>
	);
}

export function QueryCard({
	workflow,
	sortKeys,
	queryStatus,
	addSortKey,
	removeSortKey,
	setSortKeyField,
	setSortKeyDirection,
	applyFrame,
}: {
	workflow: WorkflowResponse;
	sortKeys: readonly SortKey[];
	queryStatus: QueryStatus;
	addSortKey: () => void;
	removeSortKey: (index: number) => void;
	setSortKeyField: (index: number, fieldName: string) => void;
	setSortKeyDirection: (index: number, direction: SortDirection) => void;
	applyFrame: () => void;
}) {
	return (
		<Card>
			<CardHeader>
				<CardTitle>Query</CardTitle>
				<CardDescription>Sort by up to three scalar workflow fields.</CardDescription>
			</CardHeader>
			<CardContent>
				<SortControls
					workflow={workflow}
					sortKeys={sortKeys}
					addSortKey={addSortKey}
					removeSortKey={removeSortKey}
					setSortKeyField={setSortKeyField}
					setSortKeyDirection={setSortKeyDirection}
				/>
				{queryStatus.status === "error" && (
					<ErrorBlock title="Query failed" message={queryStatus.message} />
				)}
			</CardContent>
			<CardFooter className="justify-end">
				<Button
					type="button"
					disabled={queryStatus.status === "submitting"}
					onClick={applyFrame}
				>
					{queryStatus.status === "submitting" ? "Applying…" : "Apply frame"}
				</Button>
			</CardFooter>
		</Card>
	);
}
