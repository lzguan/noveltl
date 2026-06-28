import type { SegmentManager } from "@/edit/lib/text-model/core/segmentManager";
import type { StyledLabel } from "@/edit/lib/text-model/core/types";
import type { LGProvId, LProvId } from "../controller/types/idTypes";
import type { LabelStyle } from "../managers/editorManager";
import type { LabelGroupView } from "../hooks/useTrackedLabelGroups";
import type { AddTarget, EditorLabel, LabelSource } from "./types";

type SM = SegmentManager<LabelStyle, StyledLabel<LabelStyle>, LProvId>;

function findActiveGroup(groups: Map<LGProvId, LabelGroupView>): AddTarget | null {
	for (const [labelGroupId, view] of groups) {
		if (view.active) {
			return { labelGroupId, groupName: view.labelGroup.labelGroupName, color: view.color };
		}
	}
	return null;
}

/**
 * Default {@link LabelSource}: resolves only the active label group. Hit-testing
 * uses the SegmentManager's `active` style flag (set only for the active group),
 * so no separate label->group index is needed.
 *
 * Swap this out for a richer resolver (e.g. all overlapping groups) without
 * touching the editor.
 */
export function makeActiveGroupLabelSource(opts: {
	getSegmentManager: () => SM | null;
	getGroups: () => Map<LGProvId, LabelGroupView>;
}): LabelSource {
	return {
		addTargets() {
			const active = findActiveGroup(opts.getGroups());
			return active ? [active] : [];
		},
		labelsAt(pos) {
			const sm = opts.getSegmentManager();
			const active = findActiveGroup(opts.getGroups());
			if (!sm || !active) return [];
			const text = sm.getText();
			const out: EditorLabel[] = [];
			for (const id of sm.labelsAt(pos)) {
				const label = sm.getLabel(id);
				if (!label.style[1].active) continue;
				const { start, end } = label.interval;
				out.push({ ...active, start, end, word: text.slice(start, end) });
			}
			return out;
		},
	};
}
