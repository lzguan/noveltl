import type { WorkflowSummary } from "@/api/models";
import { Badge } from "@/components/ui/badge";
import {
	Combobox,
	ComboboxCollection,
	ComboboxContent,
	ComboboxEmpty,
	ComboboxInput,
	ComboboxItem,
	ComboboxList,
} from "@/components/ui/combobox";
import { Field, FieldLabel } from "@/components/ui/field";
import { Button } from "@/components/ui/button";
import { RefreshCw } from "lucide-react";
import { ErrorBlock, statusVariant, workflowLabel } from "./panelUi";
import type { Loadable } from "../types";

export function WorkflowPicker({
	workflows,
	searchText,
	activeWorkflowId,
	setWorkflowSearchText,
	selectWorkflow,
	refreshWorkflowList,
}: {
	workflows: Loadable<readonly WorkflowSummary[]>;
	searchText: string;
	activeWorkflowId: string | null;
	setWorkflowSearchText: (searchText: string) => void;
	selectWorkflow: (workflowId: string) => void;
	refreshWorkflowList: () => void;
}) {
	if (workflows.status === "error")
		return <ErrorBlock title="Could not load workflows" message={workflows.message} />;
	const items = workflows.status === "ready" ? workflows.data : [];
	const selected = items.find((item) => item.workflowId === activeWorkflowId) ?? null;
	return (
		<Field>
			<FieldLabel htmlFor="workflow-picker">Workflow</FieldLabel>
			<div className="flex items-center gap-2">
				<div className="min-w-0 flex-1">
					<Combobox
						items={items}
						value={selected}
						inputValue={searchText}
						onInputValueChange={setWorkflowSearchText}
						onValueChange={(value) => {
							if (value) selectWorkflow(value.workflowId);
						}}
						itemToStringLabel={workflowLabel}
						isItemEqualToValue={(item, value) => item.workflowId === value.workflowId}
						disabled={workflows.status === "loading"}
					>
						<ComboboxInput
							id="workflow-picker"
							className="w-full"
							placeholder={
								workflows.status === "loading"
									? "Loading workflows…"
									: "Search workflows"
							}
							showClear
						/>
						<ComboboxContent>
							<ComboboxEmpty>No workflows found.</ComboboxEmpty>
							<ComboboxList>
								<ComboboxCollection>
									{(item: WorkflowSummary) => (
										<ComboboxItem key={item.workflowId} value={item}>
											<span className="min-w-0 flex-1 truncate">
												{workflowLabel(item)}
											</span>
											<Badge variant={statusVariant(item.workflowStatus)}>
												{item.workflowStatus}
											</Badge>
										</ComboboxItem>
									)}
								</ComboboxCollection>
							</ComboboxList>
						</ComboboxContent>
					</Combobox>
				</div>
				<Button
					type="button"
					variant="outline"
					size="icon"
					disabled={workflows.status === "loading"}
					onClick={refreshWorkflowList}
					aria-label="Refresh workflows"
				>
					<RefreshCw data-icon="inline-start" />
				</Button>
			</div>
		</Field>
	);
}
