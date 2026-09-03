import type { IChangeEvent } from "@rjsf/core";
import { Form } from "@rjsf/shadcn";
import type { RJSFSchema, UiSchema } from "@rjsf/utils";
import validator from "@rjsf/validator-ajv8";
import { useState } from "react";

import type { MemoryAgentToolsetOption } from "@/api/models";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";

const uiSchema: UiSchema = {
	"ui:submitButtonOptions": { norender: true },
};

function isObject(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isRjsfSchema(value: Record<string, unknown>): value is RJSFSchema {
	if (value.type !== "object") return false;
	return !("properties" in value) || isObject(value.properties);
}

export function toolsetHasConfig(toolset: MemoryAgentToolsetOption) {
	const properties = toolset.configSchema.properties;
	return isObject(properties) && Object.keys(properties).length > 0;
}

export function ToolsetConfigDialog({
	toolset,
	value,
	onSave,
	onClose,
}: {
	toolset: MemoryAgentToolsetOption;
	value: Record<string, unknown>;
	onSave: (value: Record<string, unknown>) => void;
	onClose: () => void;
}) {
	const schema = isRjsfSchema(toolset.configSchema) ? toolset.configSchema : null;
	const [draft, setDraft] = useState(value);
	const [valid, setValid] = useState(() =>
		schema === null ? false : validator.isValid(schema, value, schema),
	);

	return (
		<Dialog open onOpenChange={(open) => !open && onClose()}>
			<DialogContent className="max-h-[calc(100vh-2rem)] overflow-y-auto sm:max-w-lg">
				<DialogHeader>
					<DialogTitle>Configure {toolset.label}</DialogTitle>
					<DialogDescription>{toolset.description}</DialogDescription>
				</DialogHeader>
				{schema === null ? (
					<Alert variant="destructive">
						<AlertDescription>
							The server returned an unsupported configuration schema.
						</AlertDescription>
					</Alert>
				) : (
					<Form
						schema={schema}
						uiSchema={uiSchema}
						validator={validator}
						formData={draft}
						liveValidate
						noHtml5Validate
						showErrorList={false}
						tagName="div"
						onChange={({ formData, errors }: IChangeEvent<Record<string, unknown>>) => {
							setValid(errors.length === 0);
							if (formData !== undefined) setDraft(formData);
						}}
					/>
				)}
				<DialogFooter>
					<Button type="button" variant="outline" onClick={onClose}>
						Cancel
					</Button>
					<Button type="button" disabled={!valid} onClick={() => onSave(draft)}>
						Save configuration
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
