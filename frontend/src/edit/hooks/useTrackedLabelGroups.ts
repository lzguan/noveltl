import type { Color } from "@/edit/lib/text-model/builtin/colors";
import type { LGProvId, ProvLabelGroup } from "../controller/types/idTypes";
import { useCallback, useRef, useState } from "react";
import { useSyncState } from "../utils/useSyncState";

export type LabelGroupView = {
	readonly labelGroup: Omit<ProvLabelGroup, "labelGroupId" | "novelId">;
	readonly color: Color;
	readonly visible: boolean;
	readonly status: "ready" | "error" | "idle" | "loading";
};

export function useTrackedLabelGroups() {
	const [labelGroups, setLabelGroups] = useState<[LGProvId, LabelGroupView][]>([]);
	const labelGroupsRef = useRef<Map<LGProvId, LabelGroupView>>(new Map());

	const [activeLabelGroupId, activeLabelGroupIdRef, commitActiveLabelGroupId] =
		useSyncState<LGProvId | null>(null);

	const setActive = useCallback(
		(id: LGProvId | null) => {
			activeLabelGroupIdRef.current = id;
			commitActiveLabelGroupId();
		},
		[activeLabelGroupIdRef, commitActiveLabelGroupId],
	);

	const set = useCallback((id: LGProvId, entry: LabelGroupView) => {
		const curEntry = labelGroupsRef.current.get(id);
		if (
			curEntry &&
			curEntry.labelGroup === entry.labelGroup &&
			curEntry.color === entry.color &&
			curEntry.visible === entry.visible &&
			curEntry.status === entry.status
		) {
			// Nothing changed; skip to avoid a redundant re-render.
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
	const remove = useCallback(
		(id: LGProvId) => {
			if (!labelGroupsRef.current.has(id)) return;
			labelGroupsRef.current.delete(id);
			if (activeLabelGroupIdRef.current === id) {
				activeLabelGroupIdRef.current = null;
				commitActiveLabelGroupId();
			}
			setLabelGroups((prev) => prev.filter(([lgId]) => lgId !== id));
		},
		[activeLabelGroupIdRef, commitActiveLabelGroupId],
	);

	return {
		labelGroups,
		setLabelGroup: set,
		removeLabelGroup: remove,
		labelGroupsRef,
		activeLabelGroupId,
		setActive,
		activeLabelGroupIdRef,
	};
}
