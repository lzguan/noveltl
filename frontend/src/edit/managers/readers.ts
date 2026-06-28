import { Effect } from "effect";
import type { Color } from "@/edit/lib/text-model/builtin/colors";
import type { ManagedLabel } from "@/edit/lib/text-model/core/segmentManager";
import type { StyledLabel } from "@/edit/lib/text-model/core/types";
import type { LGProvId, LProvId, ProvLabel } from "../controller/types/idTypes";
import type { LabelStyle } from "./editorManager";
import type { LabelGroupView } from "../hooks/useTrackedLabelGroups";
import type { ChapterGetterSlot } from "../controller/types/helperTypes";

type MyManagedLabel = ManagedLabel<LabelStyle, StyledLabel<LabelStyle>, LProvId>;

export function makeStyledLabel(
	label: { labelId: LProvId; labelStart: number; labelEnd: number },
	color: Color,
	active: boolean,
	visible: boolean,
): MyManagedLabel {
	return {
		interval: { start: label.labelStart, end: label.labelEnd },
		style: [
			{ color },
			{
				cursorStatus: "none" as const,
				active,
				visible,
			},
		],
		id: label.labelId,
	};
}

export function gatherLabelData(
	chapterGetter: ChapterGetterSlot,
	trackedLabelGroups: Map<LGProvId, LabelGroupView>,
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
				slotResult.data.labels.map((label: ProvLabel) =>
					makeStyledLabel(
						label,
						groupStatus.color,
						groupStatus.active,
						groupStatus.visible,
					),
				),
			);
		}

		return { labelData, couldNotLoad };
	});
}
