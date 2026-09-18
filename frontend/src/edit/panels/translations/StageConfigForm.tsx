import { readUI } from "./schemaUi";
import { useState } from "react";
import type { IChangeEvent } from "@rjsf/core";
import { Form } from "@rjsf/shadcn";
import type { RJSFSchema, UiSchema } from "@rjsf/utils";
import validator from "@rjsf/validator-ajv8";
import { ConfigSelectWidget } from "./ConfigSelectWidget";
import { ConfigNumberWidget } from "./ConfigNumberWidget";
import { ConfigFilterField } from "./ConfigFilterField";

export function StageConfigForm({
	schema,
	config,
	onSave,
}: {
	schema: RJSFSchema;
	config: Record<string, unknown>;
	onSave: (config: Record<string, unknown>) => void;
}) {
	const [draft, setDraft] = useState(config);
	const properties = schema.properties ?? {};
	const hidden = Object.entries(properties)
		.filter(([, field]) => {
			const dependency = readUI(field).showAfter;
			return (
				dependency !== undefined &&
				(draft[dependency] === undefined ||
					draft[dependency] === null ||
					draft[dependency] === "")
			);
		})
		.map(([name]) => name);
	const awaitingSelection = hidden.length > 0;
	const visibleSchema: RJSFSchema = {
		...schema,
		properties: Object.fromEntries(
			Object.entries(properties).filter(([name]) => !hidden.includes(name)),
		),
		required: schema.required?.filter((name) => !hidden.includes(name)),
	};
	const uiSchema: UiSchema = {
		"ui:submitButtonOptions": {
			submitText: "Save configuration",
			props: { disabled: awaitingSelection },
		},
	};
	for (const [name, field] of Object.entries(visibleSchema.properties ?? {})) {
		const ui = readUI(field);
		const options = { "ui:placeholder": ui.placeholder };
		switch (ui.control) {
			case "number":
				uiSchema[name] = { ...options, "ui:widget": ConfigNumberWidget };
				break;
			case "filter-checklist":
				uiSchema[name] = { ...options, "ui:field": ConfigFilterField };
				break;
			case "text":
			case "textarea":
			case "select":
			case "checkbox":
				uiSchema[name] = { ...options, "ui:widget": ui.control };
				break;
		}
	}
	return (
		<>
			{awaitingSelection && (
				<p className="text-sm text-muted-foreground">
					Choose a value for the selector above to configure this stage.
				</p>
			)}
			<Form
				schema={visibleSchema}
				validator={validator}
				widgets={{ SelectWidget: ConfigSelectWidget }}
				formData={Object.fromEntries(
					Object.entries(draft).filter(([name]) => !hidden.includes(name)),
				)}
				uiSchema={uiSchema}
				onChange={({ formData }: IChangeEvent<Record<string, unknown>>) => {
					if (formData)
						setDraft((current) => ({
							...Object.fromEntries(
								Object.entries(current).filter(([name]) => hidden.includes(name)),
							),
							...formData,
						}));
				}}
				onSubmit={({ formData }: IChangeEvent<Record<string, unknown>>) => {
					if (formData && !awaitingSelection) onSave(formData);
				}}
			/>
		</>
	);
}
