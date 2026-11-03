import { ConventionCategory } from "@/api/models";

export const CONVENTION_CATEGORY_OPTIONS: readonly { label: string; value: ConventionCategory }[] =
	[
		{ label: "Naming", value: ConventionCategory.naming },
		{ label: "Style", value: ConventionCategory.style },
	];

export function isConventionCategory(value: string): value is ConventionCategory {
	return Object.values(ConventionCategory).some((candidate) => candidate === value);
}
