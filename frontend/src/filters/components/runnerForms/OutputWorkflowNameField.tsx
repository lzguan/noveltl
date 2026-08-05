import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

export function OutputWorkflowNameField({
	id,
	outputWorkflowName,
	disabled,
	setOutputWorkflowName,
}: {
	id: string;
	outputWorkflowName: string;
	disabled: boolean;
	setOutputWorkflowName: (name: string) => void;
}) {
	return (
		<Field>
			<FieldLabel htmlFor={id}>Output workflow name</FieldLabel>
			<Input
				id={id}
				name="outputName"
				value={outputWorkflowName}
				onChange={(event) => setOutputWorkflowName(event.target.value)}
				disabled={disabled}
				maxLength={100}
				autoComplete="off"
				placeholder="Optional name"
			/>
			<FieldDescription>Optional. Blank names are omitted from the request.</FieldDescription>
		</Field>
	);
}
