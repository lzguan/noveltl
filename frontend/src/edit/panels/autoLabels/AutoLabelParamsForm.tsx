import { useEffect, useMemo, useState } from "react";
import type { IChangeEvent } from "@rjsf/core";
import type { RJSFSchema, UiSchema } from "@rjsf/utils";
import { Form } from "@rjsf/shadcn";
import validator from "@rjsf/validator-ajv8";
import { JsonSchema, Result, Schema, SchemaAST, SchemaRepresentation } from "effect";
import { CreateAutolabelsAutoLabelsPostBody } from "@/api/endpoints/default/default.effect";
import type { CreateAutoLabels } from "@/api/models";
import { autoLabelCustomParamFields } from "./autoLabelParamFields";

export type AutoLabelParams = CreateAutoLabels["params"];
export type AutoLabelParamsValue = AutoLabelParams | null;

export interface AutoLabelParamModel {
	name: string;
	schema: RJSFSchema;
}

const paramsEffectSchema = CreateAutolabelsAutoLabelsPostBody.fields.params;
const paramsJsonSchema: RJSFSchema = JsonSchema.toDocumentDraft07(
	SchemaRepresentation.toJsonSchemaDocument(
		Schema.toRepresentation(Schema.toType(paramsEffectSchema)),
		{ onExcessProperty: "error" },
	),
).schema;

function readModelName(schema: unknown): string | null {
	if (
		typeof schema !== "object" ||
		schema === null ||
		!("type" in schema) ||
		schema.type !== "object" ||
		!("properties" in schema) ||
		typeof schema.properties !== "object" ||
		schema.properties === null ||
		!("modelName" in schema.properties)
	) {
		return null;
	}

	const modelName = schema.properties.modelName;
	if (
		typeof modelName !== "object" ||
		modelName === null ||
		!("enum" in modelName) ||
		!Array.isArray(modelName.enum) ||
		modelName.enum.length !== 1 ||
		typeof modelName.enum[0] !== "string"
	) {
		return null;
	}
	return modelName.enum[0];
}

function extractParamModels(): AutoLabelParamModel[] {
	if (!paramsJsonSchema.anyOf) {
		throw new Error("The generated autolabel params schema must be a union");
	}

	return paramsJsonSchema.anyOf.map((schema, index) => {
		if (typeof schema === "boolean") {
			throw new Error("Every autolabel params branch must be an object schema");
		}
		const name = readModelName(schema);
		if (!name) {
			throw new Error("Every autolabel params branch must have one modelName literal");
		}
		// Render decoded values while retaining the input's optional/defaulted keys.
		const required = Object.entries(paramsEffectSchema.members[index].fields)
			.filter(([, field]) => !SchemaAST.isOptional(Schema.toEncoded(field).ast))
			.map(([name]) => name);
		return { name, schema: { ...schema, required } };
	});
}

export const autoLabelParamModels = extractParamModels();

export function createAutoLabelParams(modelName: string): AutoLabelParams {
	return Schema.decodeUnknownSync(paramsEffectSchema)({ modelName });
}

function titleFromPropertyName(name: string) {
	const words = name.replace(/([a-z0-9])([A-Z])/g, "$1 $2");
	return words.charAt(0).toUpperCase() + words.slice(1);
}

function objectEntries(value: object) {
	return Object.entries(value);
}

function propertyValue(value: object, name: string): unknown {
	return objectEntries(value).find(([property]) => property === name)?.[1];
}

function makeStandardProperty(schema: RJSFSchema | boolean): RJSFSchema | boolean {
	if (typeof schema === "boolean" || schema.anyOf?.length !== 2) return schema;
	const [number, nonFinite] = schema.anyOf;
	if (
		typeof number === "boolean" ||
		number.type !== "number" ||
		typeof nonFinite === "boolean" ||
		nonFinite.type !== "string" ||
		nonFinite.enum?.length !== 3 ||
		!nonFinite.enum.every(
			(value) => value === "NaN" || value === "Infinity" || value === "-Infinity",
		)
	)
		return schema;
	// Effect models non-finite JS numbers as strings; JSON API form inputs stay numeric.
	const { anyOf: _anyOf, ...constraints } = schema;
	return { ...constraints, ...number };
}

function makeStandardSchema(schema: RJSFSchema): RJSFSchema {
	const schemaWithoutModelDescription = { ...schema };
	delete schemaWithoutModelDescription.description;
	const properties = Object.fromEntries(
		Object.entries(schema.properties ?? {})
			.filter(([name]) => name !== "modelName" && !autoLabelCustomParamFields[name])
			.map(([name, property]) => [name, makeStandardProperty(property)]),
	);
	return {
		...schemaWithoutModelDescription,
		properties,
		required: schema.required?.filter((name) => name in properties),
	};
}

function makeUiSchema(schema: RJSFSchema): UiSchema {
	const fields = Object.fromEntries(
		Object.keys(schema.properties ?? {}).map((name) => [
			name,
			{ "ui:title": titleFromPropertyName(name) },
		]),
	);
	return {
		...fields,
		"ui:submitButtonOptions": {
			norender: true,
		},
	};
}

function makeStandardFormData(value: AutoLabelParams) {
	return Object.fromEntries(
		objectEntries(value).filter(
			([name]) => name !== "modelName" && !autoLabelCustomParamFields[name],
		),
	);
}

function decodeParams(value: unknown): AutoLabelParams | null {
	const decoded = Schema.decodeUnknownResult(paramsEffectSchema)(value);
	return Result.isSuccess(decoded) ? decoded.success : null;
}

export function modelHasAdvancedSettings(model: AutoLabelParamModel) {
	return Object.keys(model.schema.properties ?? {}).some((name) => name !== "modelName");
}

export function AutoLabelParamsForm({
	model,
	value,
	onChange,
	onValidityChange,
	disabled,
}: {
	model: AutoLabelParamModel;
	value: AutoLabelParams;
	onChange: (value: AutoLabelParams) => void;
	onValidityChange: (valid: boolean) => void;
	disabled?: boolean;
}) {
	const standardSchema = useMemo(() => makeStandardSchema(model.schema), [model.schema]);
	const uiSchema = useMemo(() => makeUiSchema(standardSchema), [standardSchema]);
	const [schemaValid, setSchemaValid] = useState(true);
	const [customValidity, setCustomValidity] = useState<Record<string, boolean>>({});
	const customFields = Object.keys(model.schema.properties ?? {}).flatMap((name) => {
		const FieldComponent = autoLabelCustomParamFields[name];
		return FieldComponent ? [{ name, FieldComponent }] : [];
	});
	const paramsValid = schemaValid && Object.values(customValidity).every(Boolean);

	useEffect(() => {
		onValidityChange(paramsValid);
	}, [onValidityChange, paramsValid]);

	const updateParams = (updates: object) => {
		const decoded = decodeParams({
			...Object.fromEntries(objectEntries(value)),
			...Object.fromEntries(objectEntries(updates)),
		});
		if (decoded) onChange(decoded);
	};

	return (
		<div className="flex flex-col gap-3 rounded-md border border-border p-2">
			{Object.keys(standardSchema.properties ?? {}).length > 0 && (
				<Form
					schema={standardSchema}
					uiSchema={uiSchema}
					validator={validator}
					formData={makeStandardFormData(value)}
					disabled={disabled}
					liveValidate
					noHtml5Validate
					showErrorList={false}
					tagName="div"
					onChange={({ formData, errors }: IChangeEvent<object>) => {
						setSchemaValid(errors.length === 0);
						if (formData) updateParams(formData);
					}}
				/>
			)}
			{customFields.map(({ name, FieldComponent }) => (
				<FieldComponent
					key={name}
					value={propertyValue(value, name)}
					disabled={disabled}
					onValidityChange={(valid) =>
						setCustomValidity((current) => ({ ...current, [name]: valid }))
					}
					onChange={(nextValue) => updateParams({ [name]: nextValue })}
				/>
			))}
		</div>
	);
}
