import type { RJSFSchema } from "@rjsf/utils";

/** Unknown annotations are ignored; executable widgets and resource loaders stay local. */
export function readUI(field: RJSFSchema | boolean) {
	const value: unknown = typeof field === "object" ? field["x-ui"] : undefined;
	const hints = value && typeof value === "object" ? value : {};
	const string = (key: string) => {
		const value: unknown = Reflect.get(hints, key);
		return typeof value === "string" ? value : undefined;
	};
	return {
		control: string("control"),
		resource: string("resource"),
		scope: string("scope"),
		placement: string("placement"),
		stageScope: string("stageScope"),
		showAfter: string("showAfter"),
		placeholder: string("placeholder"),
		nullLabel: string("nullLabel"),
		emptyLabel: string("emptyLabel"),
	};
}

export function memoryGroupInputs(schema: RJSFSchema) {
	return Object.entries(schema.properties ?? {}).filter(([, field]) => {
		const ui = readUI(field);
		return (
			ui.control === "resource-picker" &&
			ui.resource === "memory-group" &&
			ui.scope === "current-novel" &&
			ui.placement === "job-inputs"
		);
	});
}
