import type { SortDirection, SortKey, WorkflowResponse } from "@/api/models";
import { useCallback, useState } from "react";

function sortableFieldNames(workflow: WorkflowResponse | null) {
	if (!workflow) return [];
	return Object.entries(workflow.schema.fields ?? {})
		.filter((entry) => {
			const type = entry[1].type;
			return type === "string" || type === "int" || type === "float" || type === "bool";
		})
		.map(([fieldName]) => fieldName);
}

export function useFrameDraft(workflow: WorkflowResponse | null) {
	const [sortKeys, setSortKeys] = useState<readonly SortKey[]>([]);

	const resetFrameDraft = useCallback(() => setSortKeys([]), []);

	function addSortKey() {
		const firstFieldName = sortableFieldNames(workflow)[0];
		if (!firstFieldName) return;
		setSortKeys((current) =>
			current.length >= 3
				? current
				: [...current, { fieldName: firstFieldName, direction: "asc" }],
		);
	}

	function removeSortKey(index: number) {
		setSortKeys((current) => current.filter((_, keyIndex) => keyIndex !== index));
	}

	function setSortKeyField(index: number, fieldName: string) {
		setSortKeys((current) =>
			current.map((sortKey, keyIndex) =>
				keyIndex === index ? { ...sortKey, fieldName } : sortKey,
			),
		);
	}

	function setSortKeyDirection(index: number, direction: SortDirection) {
		setSortKeys((current) =>
			current.map((sortKey, keyIndex) =>
				keyIndex === index ? { ...sortKey, direction } : sortKey,
			),
		);
	}

	return {
		sortKeys,
		addSortKey,
		removeSortKey,
		setSortKeyField,
		setSortKeyDirection,
		resetFrameDraft,
	};
}
