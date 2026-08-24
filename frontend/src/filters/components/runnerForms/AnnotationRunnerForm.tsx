import { runPythonAnnotation } from "@/api/endpoints/filters/filters";
import type { NewFieldRequest } from "@/api/models";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Field,
	FieldDescription,
	FieldGroup,
	FieldLabel,
	FieldLegend,
	FieldSet,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Plus, Trash2 } from "lucide-react";
import { apiErrorMessage, requestErrorMessage } from "../../apiErrors";
import { useAnnotationRunnerForm } from "../../hooks/runnerForms/useAnnotationRunnerForm";
import { WorkflowSearchSelector } from "./RunnerSelectors";
import { RunnerFormShell } from "./RunnerFormShell";

export function AnnotationRunnerForm({ novelId, enabled }: { novelId: string; enabled: boolean }) {
	const props = useAnnotationRunnerForm(novelId, enabled);
	const submitting = props.formStatus.status === "submitting";

	function buildNewFields() {
		if (!props.selectedWorkflow) throw new Error("Select a workflow.");
		if (props.fields.length === 0) throw new Error("Add at least one annotation field.");
		const newFields: Record<string, NewFieldRequest> = {};
		for (const field of props.fields) {
			const name = field.name.trim();
			if (!name) throw new Error("Every annotation field needs a name.");
			if (name.length > 128) throw new Error(`Field '${name}' exceeds 128 characters.`);
			if (name in newFields) throw new Error(`Annotation field '${name}' is duplicated.`);
			if (name in (props.selectedWorkflow.schema.fields ?? {})) {
				throw new Error(`Field '${name}' already exists in the workflow.`);
			}

			if (field.type === "string") {
				newFields[name] = {
					type: "string",
					defaultValue: typeof field.defaultValue === "string" ? field.defaultValue : "",
				};
			} else if (field.type === "bool") {
				newFields[name] = { type: "bool", defaultValue: field.defaultValue === true };
			} else {
				const text = typeof field.defaultValue === "string" ? field.defaultValue : "";
				if (text.trim() === "") {
					throw new Error(`Enter a default value for '${name}'.`);
				}
				const parsed = Number(text);
				if (field.type === "int") {
					if (!Number.isInteger(parsed)) {
						throw new Error(`The default for '${name}' must be a whole number.`);
					}
					newFields[name] = { type: "int", defaultValue: parsed };
				} else {
					if (!Number.isFinite(parsed)) {
						throw new Error(`The default for '${name}' must be a finite number.`);
					}
					newFields[name] = { type: "float", defaultValue: parsed };
				}
			}
		}
		return newFields;
	}

	async function submitAnnotationRunner() {
		if (!props.selectedWorkflow) return;
		let newFields: Record<string, NewFieldRequest>;
		try {
			newFields = buildNewFields();
		} catch (error) {
			props.onSendError(requestErrorMessage(error));
			return;
		}

		props.preSend();
		try {
			const response = await runPythonAnnotation({
				workflowId: props.selectedWorkflow.workflowId,
				newFields,
			});
			if (response.status === 202) {
				props.onSendSuccess();
			} else {
				props.onSendError(
					apiErrorMessage(response.data, "Could not queue the annotation workflow."),
				);
			}
		} catch (error) {
			props.onSendError(requestErrorMessage(error));
		}
	}

	return (
		<RunnerFormShell
			title="Annotate workflow"
			description="Add mutable scalar fields and their defaults to every workflow instance."
			submitLabel="Add annotation fields"
			formStatus={props.formStatus}
			canSubmit={props.selectedWorkflow !== null && props.fields.length > 0}
			submitRunnerOperation={submitAnnotationRunner}
		>
			<WorkflowSearchSelector
				id="annotation-runner-workflow"
				label="Workflow"
				search={props.workflows}
				selectedWorkflow={props.selectedWorkflow}
				disabled={submitting}
				selectWorkflow={props.selectWorkflow}
			/>
			<FieldSet>
				<FieldLegend variant="label">New annotation fields</FieldLegend>
				<FieldDescription>
					Each field is mutable after the annotation job completes.
				</FieldDescription>
				<FieldGroup className="gap-4">
					{props.fields.map((field, index) => (
						<Field orientation="responsive" key={field.id}>
							<Field>
								<FieldLabel htmlFor={`annotation-field-name-${field.id}`}>
									Field name
								</FieldLabel>
								<Input
									id={`annotation-field-name-${field.id}`}
									value={field.name}
									disabled={submitting}
									maxLength={128}
									onChange={(event) =>
										props.setFieldName(field.id, event.target.value)
									}
								/>
							</Field>
							<Field>
								<FieldLabel>Type</FieldLabel>
								<Select
									value={field.type}
									disabled={submitting}
									onValueChange={(value) => {
										if (
											value === "string" ||
											value === "int" ||
											value === "float" ||
											value === "bool"
										)
											props.setFieldType(field.id, value);
									}}
								>
									<SelectTrigger aria-label={`Field type ${index + 1}`}>
										<SelectValue />
									</SelectTrigger>
									<SelectContent>
										<SelectGroup>
											<SelectItem value="string">String</SelectItem>
											<SelectItem value="int">Integer</SelectItem>
											<SelectItem value="float">Float</SelectItem>
											<SelectItem value="bool">Boolean</SelectItem>
										</SelectGroup>
									</SelectContent>
								</Select>
							</Field>
							<Field>
								<FieldLabel htmlFor={`annotation-default-${field.id}`}>
									Default value
								</FieldLabel>
								{field.type === "bool" ? (
									<label className="flex h-9 items-center gap-2 text-sm">
										<Checkbox
											id={`annotation-default-${field.id}`}
											checked={field.defaultValue === true}
											disabled={submitting}
											onCheckedChange={(checked) =>
												props.setFieldDefaultValue(
													field.id,
													checked === true,
												)
											}
										/>
										{field.defaultValue === true ? "true" : "false"}
									</label>
								) : (
									<Input
										id={`annotation-default-${field.id}`}
										type={field.type === "string" ? "text" : "number"}
										step={
											field.type === "int"
												? "1"
												: field.type === "float"
													? "any"
													: undefined
										}
										value={
											typeof field.defaultValue === "string"
												? field.defaultValue
												: ""
										}
										disabled={submitting}
										onChange={(event) =>
											props.setFieldDefaultValue(field.id, event.target.value)
										}
									/>
								)}
							</Field>
							<Button
								type="button"
								variant="ghost"
								size="icon-sm"
								disabled={submitting}
								onClick={() => props.removeField(field.id)}
								aria-label={`Remove annotation field ${index + 1}`}
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
					disabled={submitting || props.fields.length >= 100}
					onClick={props.addField}
				>
					<Plus data-icon="inline-start" /> Add field
				</Button>
			</FieldSet>
		</RunnerFormShell>
	);
}
