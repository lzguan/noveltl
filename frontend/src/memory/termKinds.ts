import { TermKind } from "@/api/models";

export const UNCATEGORIZED_TERM_KIND = "uncategorized";

export const TERM_KIND_OPTIONS: readonly { label: string; value: TermKind }[] = [
	{ label: "Person", value: TermKind.person },
	{ label: "Place", value: TermKind.place },
	{ label: "Organization", value: TermKind.organization },
	{ label: "Technique", value: TermKind.technique },
	{ label: "Item", value: TermKind.item },
	{ label: "Concept", value: TermKind.concept },
	{ label: "Title", value: TermKind.title },
	{ label: "Species", value: TermKind.species },
	{ label: "Other", value: TermKind.other },
];

export function isTermKind(value: string): value is TermKind {
	return Object.values(TermKind).some((candidate) => candidate === value);
}

export function termKindLabel(termKind: TermKind | null): string {
	if (termKind === null) return "Uncategorized";
	return TERM_KIND_OPTIONS.find((option) => option.value === termKind)?.label ?? termKind;
}
