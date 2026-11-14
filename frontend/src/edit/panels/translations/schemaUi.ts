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
		showAfter: string("showAfter"),
		placeholder: string("placeholder"),
		nullLabel: string("nullLabel"),
		emptyLabel: string("emptyLabel"),
	};
}
