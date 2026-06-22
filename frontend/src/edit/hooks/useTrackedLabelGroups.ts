import type { Color } from "@/components/labeled-text-lib/builtin/colors";
import type { LGProvId, ProvLabelGroup } from "../controller/types/idTypes";
import { useCallback, useRef, useState } from "react";

export type LabelGroupView = {
	readonly labelGroup: Omit<ProvLabelGroup, "labelGroupId" | "novelId">;
	readonly color: Color;
	readonly visible: boolean;
	readonly active: boolean;
	readonly status: "ready" | "error" | "idle" | "loading";
};

export function useTrackedLabelGroups() {
	const [labelGroups, setLabelGroups] = useState<[LGProvId, LabelGroupView][]>([]);
	const labelGroupsRef = useRef<Map<LGProvId, LabelGroupView>>(new Map());

	const set = useCallback((id: LGProvId, entry: LabelGroupView) => {
		const curEntry = labelGroupsRef.current.get(id);
		if (curEntry && curEntry.labelGroup === entry.labelGroup) {
			// No need to update if the label group data is the same
			return;
		} else if (curEntry) {
			labelGroupsRef.current.set(id, entry);
			setLabelGroups((prev) =>
				prev.map(([lgId, lgEntry]) => (lgId === id ? [id, entry] : [lgId, lgEntry])),
			);
		} else {
			labelGroupsRef.current.set(id, entry);
			setLabelGroups((prev) => [...prev, [id, entry]]);
		}
	}, []);
	const remove = useCallback((id: LGProvId) => {
		if (!labelGroupsRef.current.has(id)) return;
		labelGroupsRef.current.delete(id);
		setLabelGroups((prev) => prev.filter(([lgId]) => lgId !== id));
	}, []);

	return { labelGroups, setLabelGroup: set, removeLabelGroup: remove, labelGroupsRef };
}
