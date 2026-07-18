import { Effect } from "effect";
import type { ManagedLabel } from "@/edit/lib/text-model/core/segmentManager";
import type { StyledLabel } from "@/edit/lib/text-model/core/types";
import type { LGProvId, LProvId, ProvLabel } from "../controller/types/idTypes";
import type { LabelStyle } from "./editorManager";
import type { LabelGroupView } from "../hooks/useTrackedLabelGroups";
import type { ChapterGetterSlot } from "../controller/types/helperTypes";

type MyManagedLabel = ManagedLabel<LabelStyle, StyledLabel<LabelStyle>, LProvId>;

/**
 * Returns a map of label group IDs to their corresponding labels, along with a list of label group IDs that could not be loaded.
 *
 * @param chapterGetter
 * @param trackedLabelGroups
 * @param activeLabelGroupId
 * @returns
 */
export function gatherLabelData(
	chapterGetter: ChapterGetterSlot,
	trackedLabelGroups: Map<LGProvId, LabelGroupView>,
	activeLabelGroupId: LGProvId | null,
): Effect.Effect<{
	labelData: Map<LGProvId, readonly MyManagedLabel[]>;
	couldNotLoad: LGProvId[];
}> {
	return Effect.gen(function* () {
		const couldNotLoad: LGProvId[] = [];
		const labelData = new Map<LGProvId, readonly MyManagedLabel[]>();
		if (chapterGetter.status !== "ready") {
			return yield* Effect.succeed({ labelData, couldNotLoad });
		}

		for (const [labelGroupId, groupStatus] of trackedLabelGroups) {
			const slotResult = yield* chapterGetter.data.chapterGetters
				.labelDataSlot(labelGroupId)
				.pipe(Effect.catchAll(() => Effect.succeed({ status: "error" as const })));
			if (!slotResult || slotResult.status !== "ready" || !slotResult.data) {
				couldNotLoad.push(labelGroupId);
				continue;
			}
			labelData.set(
				labelGroupId,
				slotResult.data.labels.map((label: ProvLabel) => ({
					interval: { start: label.labelStart, end: label.labelEnd },
					style: [
						{ color: groupStatus.color },
						{
							cursorStatus: "none" as const,
							active: labelGroupId === activeLabelGroupId,
							visible: groupStatus.visible,
						},
					],
					id: label.labelId,
				})),
			);
		}

		return { labelData, couldNotLoad };
	});
}
