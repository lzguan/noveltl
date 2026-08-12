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
import type { AnnotationFieldType, AnnotationRunnerFormModel } from "../../types";
import { WorkflowSearchSelector } from "./RunnerSelectors";
import { RunnerFormShell } from "./RunnerFormShell";

function isAnnotationFieldType(value: string): value is AnnotationFieldType {
	return value === "string" || value === "int" || value === "float" || value === "bool";
}

export function AnnotationRunnerForm(props: AnnotationRunnerFormModel) {
	const submitting = props.formStatus.status === "submitting";
	return (
		<RunnerFormShell
			title="Annotate workflow"
			description="Add mutable scalar fields and their defaults to every workflow instance."
			submitLabel="Add annotation fields"
			formStatus={props.formStatus}
			canSubmit={props.selectedWorkflow !== null && props.fields.length > 0}
			submitRunnerOperation={props.submitAnnotationRunner}
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
										if (isAnnotationFieldType(value))
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
