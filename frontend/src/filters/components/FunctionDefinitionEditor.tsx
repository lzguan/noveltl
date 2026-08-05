import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export interface FunctionDefinitionEditorProps {
	functionNamespace: string;
	functionName: string;
	functionDefinitionText: string;
	functionDefinitionError: string | null;
	disabled: boolean;
	setFunctionNamespace: (namespace: string) => void;
	setFunctionName: (name: string) => void;
	setFunctionDefinitionText: (definitionText: string) => void;
}

export function FunctionDefinitionEditor(props: FunctionDefinitionEditorProps) {
	return (
		<FieldGroup>
			<Field>
				<FieldLabel htmlFor="function-namespace">Namespace</FieldLabel>
				<Input
					id="function-namespace"
					name="namespace"
					value={props.functionNamespace}
					onChange={(event) => props.setFunctionNamespace(event.target.value)}
					disabled={props.disabled}
					required
					maxLength={100}
					autoComplete="off"
					placeholder="glossary"
				/>
			</Field>
			<Field>
				<FieldLabel htmlFor="function-name">Name</FieldLabel>
				<Input
					id="function-name"
					name="functionName"
					value={props.functionName}
					onChange={(event) => props.setFunctionName(event.target.value)}
					disabled={props.disabled}
					required
					maxLength={100}
					autoComplete="off"
					placeholder="character-name"
				/>
			</Field>
			<Field data-invalid={props.functionDefinitionError !== null}>
				<FieldLabel htmlFor="function-definition">Function definition</FieldLabel>
				<Textarea
					id="function-definition"
					name="functionDefinition"
					value={props.functionDefinitionText}
					onChange={(event) => props.setFunctionDefinitionText(event.target.value)}
					disabled={props.disabled}
					required
					rows={14}
					spellCheck={false}
					aria-invalid={props.functionDefinitionError !== null}
					className="font-mono"
					placeholder={'{\n  "name": "literalString",\n  "value": "Alice"\n}'}
				/>
				<FieldDescription>Enter a serialized function AST as JSON.</FieldDescription>
				<FieldError>{props.functionDefinitionError}</FieldError>
			</Field>
		</FieldGroup>
	);
}
